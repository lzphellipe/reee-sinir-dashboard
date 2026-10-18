"""Índice de prioridade com dados do SINIR (2023–2025)."""
import pandas as pd
import pytest

from reee import config as C, prioridade_sinir


def _mun():
    return pd.DataFrame({
        "cod_ibge": [1, 2, 3, 4],
        "municipio": ["Grande Sem Plano", "Grande Completa", "Média", "Pequena"],
        "uf": ["MG", "MG", "SP", "SP"],
        "populacao": [500_000, 500_000, 100_000, 20_000],   # Pequena fica fora (< 80 mil)
    })


def _planos():
    # Grande Completa declarou tudo; Média declarou sem REEE, sem coleta e sem PEV
    return pd.DataFrame([
        {"cod_ibge": 2, "ano": 2024, "cita_reee": True, "cita_lr": True, "coleta_seletiva": 1, "cita_pev": True},
        {"cod_ibge": 3, "ano": 2024, "cita_reee": False, "cita_lr": False, "coleta_seletiva": 0, "cita_pev": False},
    ])


def test_so_municipios_alvo_e_anos_do_sinir():
    df = prioridade_sinir.calcular(_mun(), _planos())
    assert set(df["cod_ibge"]) == {1, 2, 3}           # Pequena (20 mil hab.) fora
    assert set(df["ano"]) == {2024}                   # só anos com planilhas do SINIR
    assert df.loc[df.cod_ibge == 1, "pontos_exigidos"].item() == 20   # 500 mil ÷ 25 mil


def test_sem_informacao_conta_como_sinal():
    df = prioridade_sinir.calcular(_mun(), _planos()).set_index("cod_ibge")
    sem_plano, completa = df.loc[1], df.loc[2]
    assert sem_plano[list(prioridade_sinir.SINAIS[:5])].tolist() == [1, 1, 1, 1, 1]
    assert completa[["sem_plano", "plano_sem_reee", "sem_coleta_seletiva", "plano_sem_pev"]].sum() == 0
    # mesma população: quem não declarou fica à frente de quem declarou tudo
    assert sem_plano["indice_prioridade"] > completa["indice_prioridade"]


def test_indice_soma_os_pesos():
    df = prioridade_sinir.calcular(_mun(), _planos()).set_index("cod_ibge")
    p = prioridade_sinir.pesos()
    assert sum(p.values()) == pytest.approx(1.0)
    r = df.loc[1]                                      # demanda máxima + todos os sinais menos passivo
    esperado = 100 * (p["demanda"] * r["demanda"] + sum(p[k] for k in prioridade_sinir.SINAIS if k != "passivo"))
    assert r["indice_prioridade"] == pytest.approx(round(esperado, 1))
    assert df["indice_prioridade"].between(0, 100).all()


def test_pevs_listados_e_passivo():
    ent = pd.DataFrame({"cod_ibge": [2, 2], "ano": [2022, 2022], "entidade": ["Green Eletron"] * 2, "pontos": [3, 2]})
    ext = pd.DataFrame({"cod_ibge": [3], "ano": [2024], "passivo": [1.0]})
    df = prioridade_sinir.calcular(_mun(), _planos(), ext, ent).set_index("cod_ibge")
    assert df.loc[2, "pevs_listados"] == 5 and df.loc[2, "sem_pev_listado"] == 0
    assert df.loc[3, "passivo"] == 1 and df.loc[1, "passivo"] == 0


@pytest.mark.recorte(2025, 2025)
def test_respeita_o_recorte_de_anos():
    assert prioridade_sinir.calcular(_mun(), _planos()).empty   # 2024 fora do recorte 2025–2025


def test_funciona_sem_os_pesos_no_config(monkeypatch):
    """config.py local sem PESOS_PRIORIDADE_SINIR (ex.: recorte próprio): usa os padrões do módulo."""
    monkeypatch.delattr(C, "PESOS_PRIORIDADE_SINIR", raising=False)
    monkeypatch.delattr(C, "CLASSES_PRIORIDADE_SINIR", raising=False)
    assert prioridade_sinir.pesos() == prioridade_sinir.PESOS_PADRAO
    assert not prioridade_sinir.calcular(_mun(), _planos()).empty


def test_sem_planos_devolve_vazio():
    assert prioridade_sinir.calcular(_mun(), None).empty
    assert list(prioridade_sinir.calcular(_mun(), pd.DataFrame()).columns) == prioridade_sinir.COLUNAS
