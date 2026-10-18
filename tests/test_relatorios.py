"""Dados reais transcritos dos relatórios do SINIR: conferência e casamento de nomes."""
import pandas as pd

from reee import config as C, relatorios, transform


def _mun():
    return transform.dim_municipio([pd.read_csv(C.RAW_IBGE / "populacao.csv", dtype=str).assign(_arquivo="p", _ano_arquivo=None)])


def test_populacao_censo_2022_completa():
    pop = pd.read_csv(C.RAW_IBGE / "populacao.csv")
    assert len(pop) == 5570 and pop["populacao"].sum() == 203_080_756
    assert pop[pop.cod_ibge == 3550308]["populacao"].item() == 11_451_999  # São Paulo
    uf = pop.assign(uf=pop.cod_ibge // 100000).groupby("uf")["populacao"].sum()
    codigos = {11: "RO", 31: "MG", 35: "SP", 53: "DF"}
    for c, sig in codigos.items():
        assert uf[c] == C.POP_UF_CENSO_2022[sig]


def test_relatorios_conferem_e_casam_nomes():
    q = {}
    rel = relatorios.carregar(_mun(), q)
    ue = rel["uf_entidade"]
    assert ue[(ue.ano == 2022) & (ue.entidade == "ABREE")]["pontos"].sum() == 4997
    assert ue[(ue.ano == 2022) & (ue.entidade == "Green Eletron")]["pontos"].sum() == 1152
    assert ue[(ue.ano == 2023) & (ue.entidade == "Green Eletron")]["municipios_atendidos"].sum() == 306
    assert q["relatorio_municipios_nao_casados"] == []
    assert "Guarupuava/PR → Guarapuava" in q["relatorio_municipios_nome_corrigido"]
    assert len(rel["mun_entidade"]) == 266


def test_anos_com_dados_parciais_nao_mostram_cobertura(tmp_path, monkeypatch):
    import json
    from reee import pipeline
    for nome in ("PROCESSED", "POWERBI", "DASHBOARD_DATA"):
        monkeypatch.setattr(C, nome, tmp_path / nome.lower())
    monkeypatch.setattr(C, "RAW_SINIR", tmp_path / "sinir")  # sem planilhas: usa só os relatórios
    import shutil
    shutil.copytree(C.ROOT / "data" / "raw" / "sinir" / "relatorios", tmp_path / "sinir" / "relatorios")
    pipeline.executar()
    d = json.loads((C.DASHBOARD_DATA / "dashboard.json").read_text(encoding="utf-8"))
    br = {r["ano"]: r for r in d["brasil_ano"]}
    assert br[2022]["dados_parciais"] is False and br[2022]["cobertura_nominal"] > 100
    assert br[2024]["pontos"] == 1611 and br[2024]["municipios_atendidos"] == 366
    for ano in (2023, 2024):  # só a Green Eletron divulgou: a razão subestimaria a cobertura
        assert br[ano]["dados_parciais"] is True and br[ano]["cobertura_nominal"] is None


def test_massa_zero_com_pontos_vira_sem_dado(tmp_path, monkeypatch):
    """Massa 2024 gravada como 0 (ex.: CSV salvo pelo Excel) não pode aparecer como coleta zero."""
    import json
    import shutil
    from reee import pipeline
    for nome in ("PROCESSED", "POWERBI", "DASHBOARD_DATA"):
        monkeypatch.setattr(C, nome, tmp_path / nome.lower())
    monkeypatch.setattr(C, "RAW_SINIR", tmp_path / "sinir")
    rel = tmp_path / "sinir" / "relatorios"
    shutil.copytree(C.ROOT / "data" / "raw" / "sinir" / "relatorios", rel)
    csv = rel / "totais_nacionais.csv"
    # Lê sem depender da formatação do arquivo (separador, BOM, aspas, CRLF, "0" ou vazio),
    # grava a massa de 2024 como 0 e salva de novo no formato que o pipeline lê.
    nac = pd.read_csv(csv, dtype=str, sep=None, engine="python", encoding="utf-8-sig", keep_default_na=False)
    alvo = (nac["ano"].str.strip() == "2024") & (nac["entidade"].str.strip() == "Green Eletron")
    assert alvo.sum() == 1, "totais_nacionais.csv precisa ter uma linha de 2024 da Green Eletron"
    nac.loc[alvo, "toneladas"] = "0"
    nac.to_csv(csv, index=False, encoding="utf-8")
    pipeline.executar()
    d = json.loads((C.DASHBOARD_DATA / "dashboard.json").read_text(encoding="utf-8"))
    br = {r["ano"]: r for r in d["brasil_ano"]}
    assert br[2024]["pontos"] == 1611
    assert br[2024]["toneladas"] is None and br[2024]["kg_hab"] is None
    assert br[2023]["toneladas"] == 4279.67      # massa publicada continua intacta
