"""Planos municipais do SINIR (texto livre): classificação e casamento de nomes."""
import shutil

import pandas as pd
import pytest

from reee import config as C, planos_sinir, transform

COLS_DIAG = ["Declaração", "Ano", "Ano Referencia", "Data Criação", "Data Entrega", "Declarante",
             "Município Declarante", "UF Declarante", "orr_descricao", "Possui Coleta Seletiva Implantada",
             "Meta - Programa", "Meta - Programa - Descritivo"]
COLS_SOL = ["Declaração", "Ano", "Ano Referencia", "Declarante", "Município Declarante", "UF Declarante",
            "Possui Soluções Compartilhadas", "Solução", "Solução Consórcio"]


@pytest.mark.parametrize("texto,reee", [
    ("CAMPANHA DE RECOLHA DE LIXO ELETRONICO", True),
    ("Coleta seletiva de pneus, lâmpadas, pilhas e eletroeletrônicos", True),
    ("coleta seletiva de pneus, lampâdas e eletrônicos", True),
    ("DESTINAÇÃO ADEQUADA DE ELETROELETRÔNICOS", True),
    ("Implantar nota fiscal eletrônica e o MTR eletrônico", False),
    ("Sistema eletrônico de controle de pesagem", False),
    ("Logística reversa de pneus inservíveis", False),
])
def test_classificacao(texto, reee):
    assert planos_sinir.classificar(texto)[0] is reee


def _mun():
    return transform.dim_municipio([pd.read_csv(C.RAW_IBGE / "populacao.csv", dtype=str).assign(_arquivo="p", _ano_arquivo=None)])


def _gravar(caminho, colunas, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(linhas, columns=colunas)
    df = pd.concat([pd.DataFrame([colunas], columns=colunas), df])  # cabeçalho repetido, como no SINIR 2021
    df.to_csv(caminho, sep=";", index=False, encoding="latin-1")


@pytest.fixture()
def pasta(tmp_path):
    base = dict(zip(COLS_DIAG, [""] * len(COLS_DIAG)))
    def diag(mun, uf, prog, desc=""):
        return [{**base, "Município Declarante": mun, "UF Declarante": uf, "Meta - Programa": prog,
                 "Meta - Programa - Descritivo": desc}[c] for c in COLS_DIAG]
    _gravar(tmp_path / "2021" / "Municipal - Diagnostico - 2021.csv", COLS_DIAG, [
        diag("Guaranésia", "MG", "Coleta seletiva", "CAMPANHA DE RECOLHA DE LIXO ELETRONICO no centro"),
        diag("Guaranésia", "MG", "Educação ambiental"),
        diag("SAO SEBASTIAO DO PARAISO", "Minas Gerais", "Implantar nota fiscal eletrônica"),
        diag("Mogi Guaçú", "SP", "Ecoponto para resíduos eletroeletrônicos"),   # grafia errada
        diag("Cidade Inexistente", "SP", "lixo eletrônico"),
    ])
    sol = dict(zip(COLS_SOL, [""] * len(COLS_SOL)))
    _gravar(tmp_path / "2022" / "Municipal - Solucoes Compartilhadas e Custos - 2022.csv", COLS_SOL, [
        [{**sol, "Município Declarante": "Guaranésia - MG", "UF Declarante": "MG",
          "Solução Consórcio": "Logística reversa de embalagens"}[c] for c in COLS_SOL],
    ])
    (tmp_path / "2022" / "Estadual - Fluxo de Residuos - 2022.csv").write_text("UF;Descrição\nMG;eletrônicos\n", encoding="latin-1")
    return tmp_path


def test_processa_planos(pasta):
    q = {}
    p = planos_sinir.processar(_mun(), q, pasta).set_index(["cod_ibge", "ano"])
    guaranesia, paraiso, mogi = 3128303, 3164704, 3530706
    assert p.loc[(guaranesia, 2021), "cita_reee"] and "LIXO ELETRONICO" in p.loc[(guaranesia, 2021), "trecho"]
    assert not p.loc[(paraiso, 2021), "cita_reee"]          # nota fiscal eletrônica não conta
    assert p.loc[(mogi, 2021), "cita_reee"]                  # "Mogi Guaçú" casado por aproximação
    assert not p.loc[(guaranesia, 2022), "cita_reee"] and p.loc[(guaranesia, 2022), "cita_lr"]
    assert "Cidade Inexistente/SP" in q["planos_nao_casados"]
    assert len(p) == 4                                       # arquivo estadual ignorado; cabeçalho repetido ignorado


def test_pipeline_publica_planos(pasta, tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    (raw / "ibge").mkdir(parents=True)
    for f in ("municipios_kelvins.csv", "estados_kelvins.csv", "populacao.csv"):
        shutil.copy(C.RAW_IBGE / f, raw / "ibge" / f)
    shutil.copytree(C.RAW_GEO, raw / "geo")
    shutil.copytree(C.RAW_SINIR / "relatorios", raw / "sinir" / "relatorios")
    shutil.copytree(pasta, raw / "sinir" / "extraido", ignore=shutil.ignore_patterns("raw"))
    for nome, valor in {"RAW_SINIR": raw / "sinir", "RAW_IBGE": raw / "ibge", "RAW_GEO": raw / "geo",
                        "PROCESSED": tmp_path / "proc", "POWERBI": tmp_path / "proc" / "powerbi",
                        "DASHBOARD_DATA": tmp_path / "dash"}.items():
        monkeypatch.setattr(C, nome, valor)
    from reee.pipeline import executar
    pacote = executar()
    assert pacote["meta"]["fonte"] == "relatorios_entidades"
    assert any(r[:3] == [3128303, 2021, 1] and "ELETRONICO" in r[4] for r in pacote["planos_mun"])
    mg = [r for r in pacote["planos_uf"] if r["uf"] == "MG" and r["ano"] == 2021][0]
    assert mg["planos_declarados"] == 2 and mg["planos_citam_reee"] == 1
    assert (tmp_path / "dash" / "abertos" / "planos_municipais_reee.csv").exists()
