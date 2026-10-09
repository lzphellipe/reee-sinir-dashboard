"""Funções do Azure (function_app.py) testadas sem o runtime: armazenamento local no lugar do Blob."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

func = pytest.importorskip("azure.functions")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import function_app  # noqa: E402
from reee import config as C, nuvem  # noqa: E402


def chamar(nome, *args):
    fb = getattr(function_app, nome)
    return fb.build().get_user_function()(*args)


def req(metodo, url, rota=None, params=None):
    return func.HttpRequest(method=metodo, url=url, body=b"", route_params=rota or {}, params=params or {})


class Fila:
    def __init__(self):
        self.valor = None

    def set(self, v):
        self.valor = v


@pytest.fixture(autouse=True)
def armazenamento(tmp_path, monkeypatch):
    monkeypatch.setattr(nuvem, "_ARMAZ", nuvem.ArmazenamentoLocal(tmp_path / "blob"))
    return tmp_path / "blob"


def test_painel_serve_pagina_e_dados_empacotados():
    r = chamar("painel", req("GET", "/", {"caminho": ""}))
    assert r.status_code == 200 and b"Painel REEE Brasil" in r.get_body()
    assert r.headers["Content-Type"].startswith("text/html")
    r = chamar("painel", req("GET", "/data/dashboard.json", {"caminho": "data/dashboard.json"}))
    assert r.status_code == 200 and json.loads(r.get_body())["meta"]["fonte"]
    r = chamar("painel", req("GET", "/js/app.js", {"caminho": "js/app.js"}))
    assert "javascript" in r.headers["Content-Type"]


def test_painel_bloqueia_caminho_fora_do_site():
    for c in ("../function_app.py", "data/../../src/reee/config.py", "nao-existe.html"):
        assert chamar("painel", req("GET", "/" + c, {"caminho": c})).status_code == 404


def test_dados_do_blob_tem_prioridade(armazenamento):
    (armazenamento / "data").mkdir(parents=True)
    (armazenamento / "data" / "dashboard.json").write_text('{"meta": {"fonte": "blob"}}', encoding="utf-8")
    r = chamar("painel", req("GET", "/data/dashboard.json", {"caminho": "data/dashboard.json"}))
    assert json.loads(r.get_body())["meta"]["fonte"] == "blob"


def test_atualizar_enfileira_e_respeita_intervalo():
    st = json.loads(chamar("status", req("GET", "/api/status")).get_body())
    assert st["estado"] == "ocioso" and st["dados"]["fonte"]
    fila = Fila()
    r = chamar("atualizar", req("POST", "/api/atualizar"), fila)
    assert r.status_code == 202 and json.loads(fila.valor) == {"forcar": False}
    # segundo clique durante a execução
    fila2 = Fila()
    assert chamar("atualizar", req("POST", "/api/atualizar"), fila2).status_code == 409 and fila2.valor is None
    # logo depois de concluir: intervalo mínimo
    st = nuvem.ler_status()
    st.update({"estado": "concluido", "fim": datetime.now(timezone.utc).isoformat()})
    nuvem.gravar_status(st)
    r = chamar("atualizar", req("POST", "/api/atualizar"), Fila())
    assert r.status_code == 429 and "Tente de novo" in json.loads(r.get_body())["erro"]
    # execução travada há muito tempo pode ser refeita
    st.update({"estado": "executando", "inicio": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()})
    nuvem.gravar_status(st)
    assert chamar("atualizar", req("POST", "/api/atualizar"), Fila()).status_code == 202


def test_execucao_na_nuvem_publica_no_armazenamento(armazenamento):
    raiz_antes = C.RAW_SINIR
    st = nuvem.executar_atualizacao(coletar=False)   # sem internet: processa as entradas do pacote
    assert st["estado"] == "concluido", st.get("erro")
    assert st["dados"]["fonte"] == "relatorios_entidades"
    pacote = json.loads((armazenamento / "data" / "dashboard.json").read_text(encoding="utf-8"))
    assert {r["ano"]: r for r in pacote["brasil_ano"]}[2022]["pontos"] == 6149
    assert (armazenamento / "data" / "abertos" / "indicadores_uf_ano.csv").exists()
    assert (armazenamento / "relatorios" / "qualidade.json").exists()
    assert C.RAW_SINIR == raiz_antes                 # configuração restaurada
    assert json.loads((armazenamento / "status.json").read_text(encoding="utf-8"))["estado"] == "concluido"
