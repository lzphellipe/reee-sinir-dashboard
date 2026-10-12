"""Recorte de anos do painel (deploy em 2023–2025).

Os demais testes rodam em 2019–2025 (conftest.py). Estes conferem o painel com o recorte do deploy.
Cada teste fixa os anos do painel com monkeypatch, para não depender do que está no config.py.
"""
import json
import shutil
import zipfile

import pytest

from reee import config as C, etl_sinir, export

PAINEL_2023_2025 = {"ANOS_PAINEL": [2023, 2024, 2025], "ANO_BASE": 2023, "ANO_INICIAL_PAINEL": 2023}


def _painel(monkeypatch, **valores):
    for nome, valor in {**PAINEL_2023_2025, **valores}.items():
        monkeypatch.setattr(C, nome, valor)


def _pipeline_so_relatorios(tmp_path, monkeypatch):
    from reee import pipeline
    for nome in ("PROCESSED", "POWERBI", "DASHBOARD_DATA"):
        monkeypatch.setattr(C, nome, tmp_path / nome.lower())
    monkeypatch.setattr(C, "RAW_SINIR", tmp_path / "sinir")
    shutil.copytree(C.ROOT / "data" / "raw" / "sinir" / "relatorios", tmp_path / "sinir" / "relatorios")
    pipeline.executar()
    return json.loads((C.DASHBOARD_DATA / "dashboard.json").read_text(encoding="utf-8"))


@pytest.mark.recorte(2023, 2025)
def test_recorte_2023_2025_publica_so_esses_anos(tmp_path, monkeypatch):
    _painel(monkeypatch)
    d = _pipeline_so_relatorios(tmp_path, monkeypatch)
    assert sorted({r["ano"] for r in d["brasil_ano"]}) == [2023, 2024, 2025]
    assert {r["ano"] for r in d["uf_ano"]} <= {2023, 2024, 2025}
    m = d["meta"]
    assert m["anos_painel"] == [2023, 2024, 2025]
    assert m["ano_base"] == 2023
    assert m["ano_inicial_painel"] == 2023
    br = {r["ano"]: r for r in d["brasil_ano"]}
    assert br[2023]["pontos"] == 1282 and br[2024]["pontos"] == 1611
    assert br[2024]["toneladas"] is None         # massa de 2024 não publicada: vazio, nunca 0
    assert br[2025]["pontos"] is None            # nenhuma entidade publicou 2025


def test_painel_2023_2025_com_dados_desde_2019(tmp_path, monkeypatch):
    """Mesmo processando 2019–2025, o painel só mostra os anos configurados para ele."""
    _painel(monkeypatch)
    d = _pipeline_so_relatorios(tmp_path, monkeypatch)
    m = d["meta"]
    assert m["anos_painel"] == [2023, 2024, 2025] and m["ano_base"] == 2023
    br = {r["ano"]: r for r in d["brasil_ano"]}
    assert br[2023]["pontos"] == 1282


@pytest.mark.recorte(2023, 2025)
def test_anos_do_painel_seguem_o_recorte(monkeypatch):
    _painel(monkeypatch)
    assert export._anos_do_painel() == {"anos_painel": [2023, 2024, 2025], "ano_base": 2023, "ano_inicial_painel": 2023}
    # anos do painel ou ano-base fora do recorte são descartados, não viram botões vazios
    _painel(monkeypatch, ANOS_PAINEL=[2021, 2023, 2024, 2025], ANO_BASE=2021, ANO_INICIAL_PAINEL=2021)
    assert export._anos_do_painel() == {"anos_painel": [2023, 2024, 2025], "ano_base": None, "ano_inicial_painel": 2023}


@pytest.mark.recorte(2023, 2025)
def test_etl_ignora_zip_fora_do_recorte(tmp_path, monkeypatch):
    from reee import coleta
    monkeypatch.setattr(C, "PROCESSED", tmp_path / "proc")
    monkeypatch.setattr(C, "RAW_SINIR", tmp_path / "sinir")
    monkeypatch.setattr(coleta, "DIR_DOWNLOAD", tmp_path / "sinir" / "_download")
    monkeypatch.setattr(coleta, "DIR_EXTRAIDO", tmp_path / "sinir" / "extraido")
    (tmp_path / "sinir").mkdir()
    for ano in (2021, 2023, 2024):               # 2021 está fora do recorte
        with zipfile.ZipFile(tmp_path / "sinir" / f"EstadosMunicipios{ano}.zip", "w") as f:
            f.writestr("m.csv", "Município;Solução\nA;lixo eletrônico\n")
    resumo = etl_sinir.executar(progresso=lambda m: None)
    assert resumo["anos"] == [2023, 2024]