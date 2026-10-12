"""e-Participação no servidor local: POST /api/contribuicao grava e publica o CSV."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from reee import config as C, servidor


def test_servidor_local_recebe_contribuicao(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PROCESSED", tmp_path / "proc")
    monkeypatch.setattr(C, "DASHBOARD_DATA", tmp_path / "dash")
    tarefa = servidor.Tarefa()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), servidor.criar_handler(tarefa, demo=False))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/api/contribuicao"
        corpo = json.dumps({"tipo": "Sugerir novo ponto de coleta", "municipio": "Passos – MG",
                            "local": "Praça central", "descricao": "Falta ponto para eletrônicos no centro."}).encode()
        r = urllib.request.urlopen(urllib.request.Request(url, corpo, {"Content-Type": "application/json"}))
        assert r.status == 201
        assert "Passos – MG" in (tmp_path / "dash" / "abertos" / "contribuicoes.csv").read_text(encoding="utf-8-sig")
    finally:
        srv.shutdown()
