"""Coleta ponta a ponta contra um servidor falso que imita o portal do MMA (CKAN) e o SIDRA."""
import http.server
import json
import shutil
import threading
from urllib.parse import urlparse

import pandas as pd
import pytest

from reee import coleta, config as C
from test_sinir import _base, _csv_longo, _xlsx_largo  # noqa: E402

import io
import zipfile


def _zip(conteudo: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in conteudo.items():
            z.writestr(nome, dados)
    return buf.getvalue()


@pytest.fixture()
def portal_falso():
    base = _base(300)
    arquivos = {
        "estadosmunicipios2022.zip": _zip({"Municipios_2022.xlsx": _xlsx_largo(2022, base)}),
        "estadosmunicipios2023.zip": _zip({"r.csv": _csv_longo(2023, base.head(100))}),
    }
    pop = pd.read_csv(C.RAW_DEMO / "ibge_populacao_SINTETICA.csv", sep=";")
    sidra = [{"V": "Valor", "D1C": "Município (Código)"}] + [
        {"V": str(v), "D1C": str(c)} for c, v in zip(pop.iloc[:, 0], pop.iloc[:, 3])]
    contagem = {"downloads": 0}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            u = urlparse(self.path)
            porta = self.server.server_address[1]
            if u.path == "/api/3/action/package_show":
                res = [{"id": f"r{n}", "name": f"Disponibilização dos dados coletados pelo módulo Estados e Municípios - {n[-8:-4]}",
                        "url": f"http://127.0.0.1:{porta}/download/{n}", "format": "ZIP",
                        "last_modified": "2025-04-09T00:00:00"} for n in arquivos]
                res.append({"id": "x", "name": "Outro conjunto qualquer", "url": "http://127.0.0.1/x.pdf"})
                corpo, tipo = json.dumps({"success": True, "result": {"resources": res}}).encode(), "application/json"
            elif u.path.startswith("/download/"):
                contagem["downloads"] += 1
                corpo, tipo = arquivos[u.path.split("/")[-1]], "application/zip"
            elif u.path == "/sidra":
                corpo, tipo = json.dumps(sidra).encode(), "application/json"
            else:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", contagem, base
    srv.shutdown()


def test_coleta_e_pipeline_completo(portal_falso, tmp_path, monkeypatch):
    url, contagem, base = portal_falso
    raw = tmp_path / "raw"
    (raw / "ibge").mkdir(parents=True)
    for f in ("municipios_kelvins.csv", "estados_kelvins.csv"):
        shutil.copy(C.RAW_IBGE / f, raw / "ibge" / f)
    shutil.copytree(C.RAW_GEO, raw / "geo")
    for nome, valor in {"RAW_SINIR": raw / "sinir", "RAW_IBGE": raw / "ibge", "RAW_GEO": raw / "geo",
                        "PROCESSED": tmp_path / "proc", "POWERBI": tmp_path / "proc" / "powerbi",
                        "DASHBOARD_DATA": tmp_path / "dash"}.items():
        monkeypatch.setattr(C, nome, valor)
    monkeypatch.setattr(coleta, "CKAN_BASE", url)
    monkeypatch.setattr(coleta, "SIDRA_POP", url + "/sidra")
    monkeypatch.setattr(coleta, "DIR_DOWNLOAD", raw / "sinir" / "_download")
    monkeypatch.setattr(coleta, "DIR_EXTRAIDO", raw / "sinir" / "extraido")
    monkeypatch.setattr(coleta, "MANIFESTO", raw / "sinir" / "manifesto.json")

    from reee.pipeline import executar
    msgs = []
    pacote = executar(coletar=True, progresso=msgs.append)
    assert contagem["downloads"] == 2
    assert pacote["meta"]["fonte"] == "sinir_estados_municipios"
    assert set(pacote["meta"]["proveniencia"]) == {"2022", "2023"}
    br = {r["ano"]: r for r in pacote["brasil_ano"]}
    assert br[2022]["municipios_com_info"] == len(base)
    assert br[2023]["pontos"] == 300
    assert (raw / "ibge" / "populacao.csv").exists()

    # segunda execução: nada mudou no portal -> usa o cache
    msgs.clear()
    executar(coletar=True, progresso=msgs.append)
    assert contagem["downloads"] == 2
    assert any("sem alterações" in m for m in msgs)


def test_fonte_fora_do_ar_da_erro_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(coleta, "SIDRA_POP", "http://127.0.0.1:9/nada")
    monkeypatch.setattr(C, "RAW_IBGE", tmp_path)
    with pytest.raises(coleta.FonteIndisponivel, match="sem acesso a 127.0.0.1:9"):
        coleta.sincronizar_populacao(forcar=True, progresso=lambda m: None)
