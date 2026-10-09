"""Painel REEE Brasil no Azure Functions (modelo de programação Python v2).

Funções:
    painel       GET  /{*caminho}       página, CSS, JS e dados (data/...)
    status       GET  /api/status       andamento da última atualização
    atualizar    POST /api/atualizar    coloca um pedido na fila
    processar    fila reee-atualizar    coleta + pipeline + publicação no Blob
    mensal       timer (dia 1º, 06:00)  mesma atualização, agendada

As rotas são as mesmas do servidor local (src/reee/servidor.py), então o
painel funciona sem nenhuma mudança no JavaScript. O host.json remove o
prefixo "api" padrão do Functions para que "/" sirva o painel.
"""
import json
import logging
import mimetypes
import sys
from pathlib import Path

import azure.functions as func

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from reee import nuvem  # noqa: E402

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
FILA = "reee-atualizar"
SITE = RAIZ / "dashboard"
TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".json": "application/json",
         ".geojson": "application/geo+json", ".csv": "text/csv; charset=utf-8", ".svg": "image/svg+xml"}


def _json(corpo: dict, codigo: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(corpo, ensure_ascii=False), status_code=codigo,
                             mimetype="application/json", headers={"Cache-Control": "no-store"})


@app.route(route="api/status", methods=["GET"])
def status(req: func.HttpRequest) -> func.HttpResponse:
    return _json(nuvem.ler_status())


@app.route(route="api/atualizar", methods=["POST"])
@app.queue_output(arg_name="fila", queue_name=FILA, connection="AzureWebJobsStorage")
def atualizar(req: func.HttpRequest, fila: func.Out[str]) -> func.HttpResponse:
    st = nuvem.ler_status()
    ok, motivo = nuvem.pode_iniciar(st)
    if not ok:
        codigo = 409 if st.get("estado") == "executando" else 429
        return _json({**st, "erro": motivo}, codigo)
    forcar = req.params.get("forcar") == "1"
    fila.set(json.dumps({"forcar": forcar}))
    return _json(nuvem.marcar_na_fila(), 202)


@app.queue_trigger(arg_name="msg", queue_name=FILA, connection="AzureWebJobsStorage")
def processar(msg: func.QueueMessage) -> None:
    logging.info("Atualização pedida pelo painel: %s", msg.get_body().decode("utf-8", "replace"))
    nuvem.executar_atualizacao(coletar=True)


@app.timer_trigger(arg_name="timer", schedule="0 0 9 1 * *", run_on_startup=False)  # dia 1º, 09:00 UTC = 06:00 em Brasília
def mensal(timer: func.TimerRequest) -> None:
    logging.info("Atualização mensal agendada")
    nuvem.executar_atualizacao(coletar=True)


@app.route(route="{*caminho}", methods=["GET"])
def painel(req: func.HttpRequest) -> func.HttpResponse:
    caminho = (req.route_params.get("caminho") or "").strip("/") or "index.html"
    if caminho.startswith("data/"):
        achado = nuvem.arquivo_de_dados(caminho[len("data/"):])
        if achado is None:
            return func.HttpResponse("Arquivo não encontrado", status_code=404)
        dados, tipo = achado
        return func.HttpResponse(dados, mimetype=tipo.split(";")[0], charset="utf-8",
                                 headers={"Cache-Control": "no-store", "Content-Type": tipo})
    alvo = (SITE / caminho).resolve()
    if not str(alvo).startswith(str(SITE.resolve())) or not alvo.is_file():
        return func.HttpResponse("Página não encontrada", status_code=404)
    tipo = TIPOS.get(alvo.suffix, mimetypes.guess_type(alvo.name)[0] or "application/octet-stream")
    return func.HttpResponse(alvo.read_bytes(), headers={"Content-Type": tipo, "Cache-Control": "public, max-age=300"})
