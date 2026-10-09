"""Servidor local do painel com atualização de dados em tempo de execução.

    python -m reee.servidor                # abre http://localhost:8000 e atualiza se preciso
    python -m reee.servidor --porta 8080 --sem-navegador
    python -m reee.servidor --demo         # sem internet: dados sintéticos

Ao iniciar, se não houver dados reais ou se eles tiverem mais de --validade
dias, dispara a coleta + tratamento em segundo plano. O painel acompanha o
progresso por GET /api/status e recarrega sozinho quando termina.

API:
    GET  /api/status            estado, etapa atual, log e data dos dados
    POST /api/atualizar         inicia coleta + pipeline (?forcar=1 ignora cache)
Só usa a biblioteca padrão; não há dependências de servidor web.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import logging
import threading
import traceback
import webbrowser
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from . import config as C

log = logging.getLogger("reee.servidor")


class Tarefa:
    """Execução única e observável do pipeline (uma por vez)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.estado = "ocioso"   # ocioso | executando | concluido | erro
        self.etapa = ""
        self.log: list[str] = []
        self.inicio = self.fim = None
        self.erro = None

    def _registrar(self, msg: str) -> None:
        hora = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.etapa = msg
            self.log.append(f"{hora} {msg}")
            self.log = self.log[-200:]
        log.info(msg)

    def iniciar(self, demo: bool = False, forcar: bool = False) -> bool:
        with self.lock:
            if self.estado == "executando":
                return False
            self.estado, self.log, self.erro = "executando", [], None
            self.inicio, self.fim = datetime.now(timezone.utc), None
        threading.Thread(target=self._rodar, args=(demo, forcar), daemon=True).start()
        return True

    def _rodar(self, demo: bool, forcar: bool) -> None:
        from .pipeline import executar
        try:
            executar(usar_demo=demo, coletar=not demo, forcar=forcar, progresso=self._registrar)
            estado = "concluido"
        except Exception as e:  # noqa: BLE001
            self._registrar(f"ERRO: {e}")
            log.debug(traceback.format_exc())
            self.erro = str(e)
            estado = "erro"
        with self.lock:
            self.estado, self.fim = estado, datetime.now(timezone.utc)

    def status(self) -> dict:
        meta = _meta_atual()
        with self.lock:
            return {"estado": self.estado, "etapa": self.etapa, "log": self.log[-40:], "erro": self.erro,
                    "inicio": self.inicio and self.inicio.isoformat(timespec="seconds"),
                    "fim": self.fim and self.fim.isoformat(timespec="seconds"),
                    "dados": meta}


def _meta_atual() -> dict | None:
    p = C.DASHBOARD_DATA / "dashboard.json"
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            meta = json.load(f)["meta"]
        return {"fonte": meta["fonte"], "gerado_em": meta["gerado_em"]}
    except (OSError, ValueError, KeyError):
        return None


def precisa_atualizar(validade_dias: int) -> bool:
    meta = _meta_atual()
    if not meta or meta["fonte"] == "demo":
        return True
    gerado = datetime.fromisoformat(meta["gerado_em"])
    return datetime.now(timezone.utc) - gerado > timedelta(days=validade_dias)


def criar_handler(tarefa: Tarefa, demo: bool):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silencia o log de cada arquivo
            log.debug(fmt, *args)

        def end_headers(self):
            if self.path.startswith("/data/") or self.path.startswith("/api/"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, codigo: int, corpo: dict) -> None:
            dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            if urlparse(self.path).path == "/api/status":
                return self._json(200, tarefa.status())
            return super().do_GET()

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/api/atualizar":
                return self._json(404, {"erro": "rota inexistente"})
            forcar = parse_qs(url.query).get("forcar", ["0"])[0] == "1"
            iniciou = tarefa.iniciar(demo=demo, forcar=forcar)
            return self._json(202 if iniciou else 409, tarefa.status())

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description="Servidor local do Painel REEE Brasil")
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--validade", type=int, default=7, help="dias até considerar os dados desatualizados")
    ap.add_argument("--sem-atualizar", action="store_true", help="não atualizar dados ao iniciar")
    ap.add_argument("--sem-navegador", action="store_true")
    ap.add_argument("--demo", action="store_true", help="usar dados sintéticos (sem internet)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    tarefa = Tarefa()
    handler = functools.partial(criar_handler(tarefa, args.demo), directory=str(C.ROOT / "dashboard"))
    srv = http.server.ThreadingHTTPServer((args.host, args.porta), handler)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.porta}"
    log.info("Painel em %s  (Ctrl+C para encerrar)", url)
    if not args.sem_atualizar and (args.demo or precisa_atualizar(args.validade)):
        log.info("Dados ausentes ou desatualizados: iniciando atualização em segundo plano")
        tarefa.iniciar(demo=args.demo)
    if not args.sem_navegador:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("Encerrando")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
