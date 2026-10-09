import json

import numpy as np
import pandas as pd
import pytest

from reee import config as C
from reee.utils import chave_municipio, normalizar_texto, numero_br, padronizar_colunas


@pytest.mark.parametrize("entrada,esperado", [
    ("1.234,56", 1234.56), ("12,5 t", 12.5), ("1234.56", 1234.56),
    ("1.234.567", 1234567.0), (7, 7.0), ("-", np.nan), ("", np.nan),
])
def test_numero_br(entrada, esperado):
    r = numero_br(entrada)
    assert (np.isnan(r) and np.isnan(esperado)) or r == pytest.approx(esperado)


def test_normalizacao_de_nomes():
    assert normalizar_texto("  São  Sebastião do PARAÍSO ") == "sao sebastiao do paraiso"
    assert chave_municipio("Santa Bárbara d'Oeste", "sp") == chave_municipio("SANTA BARBARA D OESTE", "SP")


def test_padronizar_colunas_por_apelido():
    df = pd.DataFrame(columns=["Código IBGE", "Município", "Sigla UF", "Peso recebido (t)"])
    out = padronizar_colunas(df, C.ALIASES_MASSA)
    assert {"cod_ibge", "municipio", "uf", "toneladas"} <= set(out.columns)


@pytest.fixture(scope="module")
def pacote():
    from reee.pipeline import executar
    return executar(usar_demo=True, seed=42)


def test_pipeline_demo_gera_pacote(pacote):
    assert pacote["meta"]["fonte"] == "demo"
    assert pacote["meta"]["anos"] == C.ANOS
    m = pacote["municipios"]
    assert len(m["cod"]) == len(set(m["cod"])) > 5500
    assert all(len(r) == len(C.ANOS) for r in m["pontos"])


def test_consistencia_dos_totais(pacote):
    m = pacote["municipios"]
    total_mun = np.array(m["pontos"]).sum(axis=0)
    total_br = [r["pontos"] for r in pacote["brasil_ano"]]
    assert total_mun.tolist() == total_br


def test_indicadores_municipais():
    f = pd.read_csv(C.PROCESSED / "indicadores_municipio_ano.csv")
    assert (f["deficit_pontos"] >= 0).all()
    assert not f.duplicated(["cod_ibge", "ano"]).any()
    obrig = f[f["obrigado_decreto"]]
    assert (obrig["pontos_necessarios"] == np.ceil(obrig["populacao"] / 25_000)).all()
    assert (f.loc[~f["obrigado_decreto"], "pontos_necessarios"] == 0).all()


def test_qualidade_registra_limpeza():
    q = json.loads((C.PROCESSED / "qualidade.json").read_text(encoding="utf-8"))
    assert q["pontos_duplicados_removidos"] > 0
    assert q["pontos_codigo_recuperado_por_nome"] > 0
    assert q["pontos_sem_municipio_descartados"] == 0
