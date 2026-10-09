"""Coleta automática das fontes oficiais.

1. SINIR/MMA – portal de dados abertos (CKAN): lista os recursos do conjunto
   "sinir", baixa os arquivos anuais do módulo Estados e Municípios e os
   extrai (ZIP, RAR, ZIPs aninhados). Usa cache: só baixa de novo quando a
   data de modificação ou o tamanho do recurso mudou.
2. IBGE/SIDRA – população residente do Censo 2022 por município (tabela 4709).

Uso:
    python -m reee.coleta              # baixa/atualiza tudo
    python -m reee.coleta --forcar     # ignora o cache
Gera data/raw/sinir/manifesto.json com a proveniência de cada arquivo.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import json
import logging
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import config as C

log = logging.getLogger("reee.coleta")

# Endereços podem ser trocados por variável de ambiente (testes, espelhos, proxy)
CKAN_BASE = os.environ.get("REEE_CKAN_BASE", "https://dados.mma.gov.br")
CKAN_DATASET = os.environ.get("REEE_CKAN_DATASET", "sinir")
SIDRA_POP = os.environ.get("REEE_SIDRA_URL", "https://apisidra.ibge.gov.br/values/t/4709/n6/all/v/93/p/2022")
USER_AGENT = "PainelREEE/0.2 (+https://github.com) Python-urllib"

# Fallback caso a API do CKAN esteja fora do ar (lista conferida em 08/10/2026).
RECURSOS_CONHECIDOS = [
    (2019, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/8e21fada-1dbf-45f4-bade-e5b1611788a1/download/estadosmunicipios2019.zip"),
    (2020, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/b2220608-f67b-4180-9505-fa36e67b3df7/download/estadosmunicipios2020.zip"),
    (2021, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/0a0e4515-f260-4a94-8588-a6cc75f4f0ab/download/estadosmunicipios2021.zip"),
    (2022, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/ec454849-f29e-40e4-bf94-826292bfc092/download/estadosmunicipios2022.zip"),
    (2023, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/1cd0be36-ce60-42b1-92c5-459f2db5d532/download/estadosmunicipios2023.zip"),
    (2024, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/c87a4319-3ee2-40a5-b6bc-769c7474b6ae/download/estadosmunicipios2024.zip"),
    (2025, "https://dados.mma.gov.br/dataset/37994d86-2dc7-4a9c-94bf-d83decd3fdd7/resource/7d13e715-cbd1-4170-a70e-1674a15642e6/download/mma-relatorios-2025-1.rar"),
]

DIR_DOWNLOAD = C.RAW_SINIR / "_download"
DIR_EXTRAIDO = C.RAW_SINIR / "extraido"
MANIFESTO = C.RAW_SINIR / "manifesto.json"

Progresso = Callable[[str], None]


# --------------------------------------------------------------------------- http
class FonteIndisponivel(RuntimeError):
    """A fonte oficial não respondeu (sem internet, proxy, site fora do ar)."""


def _abrir(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise FonteIndisponivel(f"{urllib.parse.urlparse(url).netloc} respondeu HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        motivo = getattr(e, "reason", e)
        raise FonteIndisponivel(f"sem acesso a {urllib.parse.urlparse(url).netloc} ({motivo}). "
                                "Verifique a conexão com a internet ou o proxy da rede.") from e


def _get_json(url: str, tentativas: int = 3):
    for i in range(tentativas):
        try:
            with _abrir(url) as r:
                return json.loads(r.read().decode("utf-8"))
        except (FonteIndisponivel, json.JSONDecodeError) as e:
            if i == tentativas - 1:
                raise
            log.warning("Falha em %s (%s); nova tentativa", url, e)
            time.sleep(2 * (i + 1))


def _baixar(url: str, destino: Path, progresso: Progresso) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    with _abrir(url, timeout=300) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        lido, ultimo = 0, 0.0
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
            lido += len(bloco)
            if time.time() - ultimo > 1:
                pct = f" ({lido * 100 // total} %)" if total else ""
                progresso(f"Baixando {destino.name}: {lido // (1 << 20)} MB{pct}")
                ultimo = time.time()
    tmp.replace(destino)


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# --------------------------------------------------------------------------- SINIR
def _ano_do_recurso(*textos: str) -> int | None:
    for t in textos:
        anos = [int(a) for a in re.findall(r"(?<!\d)(20[12]\d)(?!\d)", t or "")]
        anos = [a for a in anos if C.ANO_INICIAL <= a <= C.ANO_FINAL]
        if anos:
            return anos[-1]
    return None


def listar_recursos(progresso: Progresso = log.info) -> list[dict]:
    """Recursos anuais do módulo Estados e Municípios, via API CKAN (com fallback)."""
    try:
        dados = _get_json(f"{CKAN_BASE}/api/3/action/package_show?id={CKAN_DATASET}")
        recursos = []
        for r in dados["result"]["resources"]:
            nome, url = r.get("name") or "", r.get("url") or ""
            if not re.search(r"estados?\s*e\s*munic|estadosmunicipios|relatorios", nome + url, re.I):
                continue
            ano = _ano_do_recurso(nome, url)
            if ano:
                recursos.append({"ano": ano, "id": r.get("id"), "nome": nome, "url": url,
                                 "formato": (r.get("format") or "").upper(),
                                 "modificado": r.get("last_modified") or r.get("metadata_modified"),
                                 "tamanho": r.get("size")})
        if recursos:
            progresso(f"API do portal do MMA: {len(recursos)} arquivos anuais encontrados")
            return sorted(recursos, key=lambda r: r["ano"])
        progresso("API do portal respondeu sem recursos reconhecíveis; usando lista conhecida")
    except Exception as e:  # noqa: BLE001 – queremos o fallback em qualquer falha
        progresso(f"API do portal do MMA indisponível ({e.__class__.__name__}); usando lista conhecida")
    return [{"ano": a, "id": None, "nome": Path(u).name, "url": u, "formato": Path(u).suffix[1:].upper(),
             "modificado": None, "tamanho": None} for a, u in RECURSOS_CONHECIDOS]


def _extrair_rar(arquivo: Path, destino: Path) -> None:
    """RAR: tenta a biblioteca rarfile, depois 7z, depois bsdtar (tar do Windows 10+)."""
    erros = []
    try:
        import rarfile  # type: ignore
        with rarfile.RarFile(arquivo) as rf:
            rf.extractall(destino)
        return
    except Exception as e:  # noqa: BLE001
        erros.append(f"rarfile: {e}")
    for cmd in (["7z", "x", "-y", f"-o{destino}", str(arquivo)],
                ["C:/Program Files/7-Zip/7z.exe", "x", "-y", f"-o{destino}", str(arquivo)],
                ["unar", "-q", "-f", "-D", "-o", str(destino), str(arquivo)],
                ["tar", "-xf", str(arquivo), "-C", str(destino)]):
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return
        except (OSError, subprocess.CalledProcessError) as e:
            erros.append(f"{cmd[0]}: {e}")
    raise RuntimeError("Não foi possível extrair o RAR. Instale o 7-Zip ou 'pip install rarfile' "
                       "com o unrar disponível. Detalhes: " + " | ".join(erros))


_PROIBIDOS_WINDOWS = re.compile(r'[<>:"|?*\x00-\x1f]')


def _nome_no_zip(info: zipfile.ZipInfo) -> str:
    """Recupera o nome original de um arquivo dentro do ZIP, seguro para o Windows.

    Sem a marca de UTF-8, o Python lê o nome como cp437. Os ZIPs do SINIR vêm
    de máquinas diferentes: alguns gravaram UTF-8 sem a marca, outros cp850
    (Windows em português). O nome só é reinterpretado quando a conversão é
    exata; nada é substituído por "?". Por fim, acentos decompostos (macOS)
    viram a forma composta e caracteres proibidos no Windows viram "_".
    """
    import unicodedata
    nome = info.filename
    if not info.flag_bits & 0x800:
        try:
            bruto = nome.encode("cp437")      # sem errors="replace": ou converte exato, ou não mexe
        except UnicodeEncodeError:
            bruto = None
        if bruto is not None:
            for enc in ("utf-8", "cp850"):
                try:
                    nome = bruto.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
    nome = unicodedata.normalize("NFC", nome)
    partes = re.split(r"[\\/]", nome)
    return "/".join(_PROIBIDOS_WINDOWS.sub("_", p).rstrip(" .") or "_" for p in partes)


def extrair(arquivo: Path, destino: Path) -> list[Path]:
    """Extrai ZIP/RAR (inclusive arquivos compactados dentro de outros) e lista as planilhas."""
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    fila = [arquivo]
    while fila:
        atual = fila.pop()
        alvo = destino if atual == arquivo else atual.with_suffix("")
        alvo.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(atual):
            with zipfile.ZipFile(atual) as z:
                for info in z.infolist():
                    # nomes de arquivos em ZIPs brasileiros costumam vir em cp437/cp850
                    nome = _nome_no_zip(info)
                    caminho = (alvo / nome).resolve()
                    if not str(caminho).startswith(str(alvo.resolve())):  # zip slip
                        continue
                    if info.is_dir():
                        caminho.mkdir(parents=True, exist_ok=True)
                        continue
                    caminho.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, open(caminho, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        elif atual.suffix.lower() == ".rar":
            _extrair_rar(atual, alvo)
        if atual != arquivo:
            atual.unlink(missing_ok=True)
        fila += [p for p in alvo.rglob("*") if p.is_file() and p.suffix.lower() in {".zip", ".rar"}]
    return sorted(p for p in destino.rglob("*") if p.suffix.lower() in {".xlsx", ".xls", ".csv", ".ods"})


def sincronizar_sinir(forcar: bool = False, progresso: Progresso = log.info) -> dict:
    manifesto = json.loads(MANIFESTO.read_text(encoding="utf-8")) if MANIFESTO.exists() else {"arquivos": {}}
    recursos = listar_recursos(progresso)
    falhas = []
    for r in recursos:
        ano = str(r["ano"])
        nome = Path(urllib.request.url2pathname(r["url"].split("?")[0])).name or f"sinir_{ano}"
        destino = DIR_DOWNLOAD / f"{ano}_{nome}"
        anterior = manifesto["arquivos"].get(ano, {})
        mudou = (forcar or not destino.exists() or anterior.get("url") != r["url"]
                 or (r["modificado"] and anterior.get("modificado") != r["modificado"])
                 or (r["tamanho"] and anterior.get("tamanho") != r["tamanho"]))
        try:
            if mudou:
                progresso(f"{ano}: baixando {nome}")
                _baixar(r["url"], destino, progresso)
            else:
                progresso(f"{ano}: sem alterações desde a última coleta")
            pasta = DIR_EXTRAIDO / ano
            if mudou or not pasta.exists():
                progresso(f"{ano}: extraindo")
                planilhas = extrair(destino, pasta)
            else:
                planilhas = sorted(p for p in pasta.rglob("*") if p.suffix.lower() in {".xlsx", ".xls", ".csv", ".ods"})
            manifesto["arquivos"][ano] = {
                **r, "arquivo_local": destino.name, "sha256": _sha256(destino),
                "bytes": destino.stat().st_size, "planilhas": [str(p.relative_to(pasta)) for p in planilhas],
                "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            progresso(f"{ano}: {len(planilhas)} planilha(s) prontas")
        except Exception as e:  # noqa: BLE001 – um ano com problema não derruba os demais
            falhas.append(f"{ano}: {e}")
            progresso(f"{ano}: FALHA – {e}")
    manifesto["atualizado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifesto["falhas"] = falhas
    MANIFESTO.parent.mkdir(parents=True, exist_ok=True)
    MANIFESTO.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto


# --------------------------------------------------------------------------- IBGE
def sincronizar_populacao(forcar: bool = False, progresso: Progresso = log.info) -> Path:
    destino = C.RAW_IBGE / "populacao.csv"
    if destino.exists() and not forcar:
        progresso("IBGE: população do Censo 2022 já disponível")
        return destino
    progresso("IBGE: consultando população do Censo 2022 (SIDRA, tabela 4709)")
    linhas = _get_json(SIDRA_POP)[1:]
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        f.write("cod_ibge,populacao\n")
        for l in linhas:
            if l.get("V", "").isdigit():
                f.write(f"{l['D1C']},{l['V']}\n")
    progresso(f"IBGE: {len(linhas)} municípios gravados")
    return destino


def sincronizar(forcar: bool = False, progresso: Progresso = log.info) -> dict:
    pop = sincronizar_populacao(forcar, progresso)
    man = sincronizar_sinir(forcar, progresso)
    return {"populacao": str(pop), "manifesto": man}


def main() -> None:
    ap = argparse.ArgumentParser(description="Baixa os dados do SINIR (MMA) e do IBGE")
    ap.add_argument("--forcar", action="store_true", help="ignora o cache e baixa tudo de novo")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sincronizar(args.forcar)


if __name__ == "__main__":
    main()
