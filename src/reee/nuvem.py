"""Execução do painel em nuvem (Azure Functions + Blob Storage).

No Azure Functions o pacote publicado é somente leitura e o /tmp é apagado
entre execuções. Por isso:

* o pipeline roda numa pasta de trabalho temporária (/tmp/reee), para onde
  são copiadas as entradas fixas do projeto (IBGE, malha das UFs, relatórios);
* os produtos (dashboard.json, dados abertos, inventário, status) são
  enviados a um contêiner do Blob Storage;
* o painel lê primeiro do Blob e, se não houver nada lá, usa os arquivos que
  vieram no pacote.

Sem a variável AzureWebJobsStorage (ou REEE_BLOB_CONEXAO), o armazenamento
cai para uma pasta local, o que permite testar tudo fora do Azure.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config as C

log = logging.getLogger("reee.nuvem")

CONTEINER = os.environ.get("REEE_BLOB_CONTEINER", "reee")
STATUS = "status.json"
COOLDOWN_MIN = int(os.environ.get("REEE_INTERVALO_MINIMO_MIN", "30"))   # entre duas atualizações pedidas pelo botão
TRAVADO_MIN = 20                                                          # "executando" há mais que isso = execução morta


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- armazenamento
class ArmazenamentoLocal:
    """Pasta local que imita o contêiner (testes e desenvolvimento)."""

    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)

    def ler(self, nome: str) -> bytes | None:
        p = self.raiz / nome
        return p.read_bytes() if p.exists() else None

    def gravar(self, nome: str, dados: bytes, tipo: str = "application/octet-stream") -> None:
        p = self.raiz / nome
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(dados)
        tmp.replace(p)


class ArmazenamentoBlob:
    def __init__(self, conexao: str, conteiner: str = CONTEINER):
        from azure.storage.blob import BlobServiceClient
        self.cliente = BlobServiceClient.from_connection_string(conexao).get_container_client(conteiner)
        try:
            self.cliente.create_container()
        except Exception:  # noqa: BLE001 – já existe
            pass

    def ler(self, nome: str) -> bytes | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return self.cliente.download_blob(nome).readall()
        except ResourceNotFoundError:
            return None

    def gravar(self, nome: str, dados: bytes, tipo: str = "application/octet-stream") -> None:
        from azure.storage.blob import ContentSettings
        self.cliente.upload_blob(nome, dados, overwrite=True,
                                 content_settings=ContentSettings(content_type=tipo, cache_control="no-store"))


_ARMAZ = None


def armazenamento():
    global _ARMAZ
    if _ARMAZ is None:
        conexao = os.environ.get("REEE_BLOB_CONEXAO") or os.environ.get("AzureWebJobsStorage")
        if conexao and conexao != "UseDevelopmentStorage=true":
            _ARMAZ = ArmazenamentoBlob(conexao)
        else:
            _ARMAZ = ArmazenamentoLocal(Path(tempfile.gettempdir()) / "reee-armazenamento")
    return _ARMAZ


# --------------------------------------------------------------------------- status
def ler_status() -> dict:
    bruto = armazenamento().ler(STATUS)
    if bruto:
        return json.loads(bruto)
    meta = _meta_empacotada()
    return {"estado": "ocioso", "etapa": "", "log": [], "erro": None, "inicio": None, "fim": None, "dados": meta}


def gravar_status(st: dict) -> None:
    armazenamento().gravar(STATUS, json.dumps(st, ensure_ascii=False).encode("utf-8"), "application/json")


def _meta_empacotada() -> dict | None:
    p = C.DASHBOARD_DATA / "dashboard.json"
    try:
        with open(p, encoding="utf-8") as f:
            meta = json.load(f)["meta"]
        return {"fonte": meta["fonte"], "gerado_em": meta["gerado_em"]}
    except (OSError, ValueError, KeyError):
        return None


def pode_iniciar(st: dict) -> tuple[bool, str]:
    """Regras do botão: uma execução por vez e um intervalo mínimo entre pedidos."""
    if st.get("estado") == "executando":
        inicio = datetime.fromisoformat(st["inicio"]) if st.get("inicio") else _agora()
        if _agora() - inicio < timedelta(minutes=TRAVADO_MIN):
            return False, "Uma atualização já está em andamento."
    if st.get("estado") == "concluido" and st.get("fim"):
        falta = datetime.fromisoformat(st["fim"]) + timedelta(minutes=COOLDOWN_MIN) - _agora()
        if falta.total_seconds() > 0:
            return False, f"Os dados foram atualizados há pouco. Tente de novo em {int(falta.total_seconds() // 60) + 1} min."
    return True, ""


def marcar_na_fila() -> dict:
    st = ler_status()
    st.update({"estado": "executando", "etapa": "Na fila para atualizar", "erro": None,
               "inicio": _agora().isoformat(timespec="seconds"), "fim": None,
               "log": [f"{datetime.now().strftime('%H:%M:%S')} Pedido de atualização recebido"]})
    gravar_status(st)
    return st


# --------------------------------------------------------------------------- execução
def _preparar_pasta_trabalho(base: Path) -> None:
    """Copia as entradas fixas do pacote para uma pasta gravável e aponta a configuração para ela."""
    origem = C.ROOT / "data" / "raw"
    for sub in ("ibge", "geo", "sinir/relatorios"):
        if (origem / sub).exists():
            shutil.copytree(origem / sub, base / "raw" / sub, dirs_exist_ok=True)
    caminhos = {
        "RAW": base / "raw", "RAW_SINIR": base / "raw" / "sinir", "RAW_IBGE": base / "raw" / "ibge",
        "RAW_GEO": base / "raw" / "geo", "RAW_DEMO": base / "raw" / "demo",
        "PROCESSED": base / "processed", "POWERBI": base / "processed" / "powerbi",
        "DASHBOARD_DATA": base / "dashboard" / "data",
    }
    for nome, valor in caminhos.items():
        setattr(C, nome, valor)
    from . import coleta
    coleta.DIR_DOWNLOAD = C.RAW_SINIR / "_download"
    coleta.DIR_EXTRAIDO = C.RAW_SINIR / "extraido"
    coleta.MANIFESTO = C.RAW_SINIR / "manifesto.json"


TIPOS = {".json": "application/json", ".geojson": "application/geo+json", ".csv": "text/csv; charset=utf-8",
         ".md": "text/markdown; charset=utf-8"}


def _publicar(base: Path) -> None:
    arm = armazenamento()
    dash = base / "dashboard" / "data"
    for p in sorted(dash.rglob("*")):
        if p.is_file() and not p.name.endswith(".tmp"):
            arm.gravar("data/" + p.relative_to(dash).as_posix(), p.read_bytes(), TIPOS.get(p.suffix, "application/octet-stream"))
    for nome in ("qualidade.json", "inventario_sinir.md"):
        if (base / "processed" / nome).exists():
            arm.gravar("relatorios/" + nome, (base / "processed" / nome).read_bytes(), TIPOS.get(Path(nome).suffix))


def executar_atualizacao(coletar: bool = True) -> dict:
    """Roda coleta + pipeline numa pasta temporária e publica no armazenamento. Atualiza o status ao longo do caminho."""
    from .pipeline import executar
    st = ler_status()
    st.update({"estado": "executando", "erro": None, "fim": None,
               "inicio": st.get("inicio") or _agora().isoformat(timespec="seconds")})
    st.setdefault("log", [])
    ultimo = [0.0]

    def progresso(msg: str) -> None:
        log.info(msg)
        st["etapa"] = msg
        st["log"] = (st["log"] + [f"{datetime.now().strftime('%H:%M:%S')} {msg}"])[-60:]
        if time.time() - ultimo[0] > 2:  # não grava o status a cada linha
            gravar_status(st)
            ultimo[0] = time.time()

    originais = {n: getattr(C, n) for n in ("RAW", "RAW_SINIR", "RAW_IBGE", "RAW_GEO", "RAW_DEMO",
                                            "PROCESSED", "POWERBI", "DASHBOARD_DATA")}
    base = Path(tempfile.mkdtemp(prefix="reee-"))
    try:
        _preparar_pasta_trabalho(base)
        progresso("Iniciando atualização na nuvem")
        pacote = executar(coletar=coletar, progresso=progresso)
        progresso("Enviando os dados para o armazenamento")
        _publicar(base)
        st.update({"estado": "concluido", "etapa": "Concluído", "fim": _agora().isoformat(timespec="seconds"),
                   "dados": {"fonte": pacote["meta"]["fonte"], "gerado_em": pacote["meta"]["gerado_em"]}})
    except Exception as e:  # noqa: BLE001
        log.exception("Falha na atualização")
        progresso(f"ERRO: {e}")
        st.update({"estado": "erro", "erro": str(e), "fim": _agora().isoformat(timespec="seconds")})
    finally:
        gravar_status(st)
        for nome, valor in originais.items():
            setattr(C, nome, valor)
        from . import coleta
        coleta.DIR_DOWNLOAD = C.RAW_SINIR / "_download"
        coleta.DIR_EXTRAIDO = C.RAW_SINIR / "extraido"
        coleta.MANIFESTO = C.RAW_SINIR / "manifesto.json"
        shutil.rmtree(base, ignore_errors=True)
    return st


# --------------------------------------------------------------------------- arquivos do painel
def arquivo_de_dados(caminho: str) -> tuple[bytes, str] | None:
    """data/<caminho>: do armazenamento, se houver; senão, do pacote."""
    caminho = caminho.strip("/")
    if ".." in Path(caminho).parts:
        return None
    tipo = TIPOS.get(Path(caminho).suffix, "application/octet-stream")
    dados = armazenamento().ler("data/" + caminho)
    if dados is not None:
        return dados, tipo
    p = (C.ROOT / "dashboard" / "data" / caminho).resolve()
    if p.is_file() and str(p).startswith(str((C.ROOT / "dashboard" / "data").resolve())):
        return p.read_bytes(), tipo
    return None
