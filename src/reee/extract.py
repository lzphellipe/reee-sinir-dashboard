"""Etapa E (Extract): leitura tolerante dos arquivos brutos.

As exportações do SINIR, das entidades gestoras e do IBGE chegam em CSV ou
XLSX, com encodings e separadores variados. Esta etapa só LÊ e anota a
origem de cada linha; nenhuma regra de negócio é aplicada aqui.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

ENCODINGS = ("utf-8-sig", "latin-1")


def ler_tabela(caminho: Path) -> pd.DataFrame:
    """Lê CSV/XLSX detectando encoding e separador. Tudo vem como texto."""
    caminho = Path(caminho)
    if caminho.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(caminho, dtype=str)
    else:
        bruto = caminho.read_bytes()
        texto = None
        for enc in ENCODINGS:
            try:
                texto = bruto.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            sep = csv.Sniffer().sniff(texto[:5000], delimiters=";,\t|").delimiter
        except csv.Error:
            sep = ";" if texto.count(";") > texto.count(",") else ","
        df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    df["_arquivo"] = caminho.name
    ano = re.search(r"(20\d{2})(?!.*20\d{2})", caminho.stem)
    df["_ano_arquivo"] = int(ano.group(1)) if ano else pd.NA
    return df


def listar(pasta: Path, padrao: str) -> list[Path]:
    pasta = Path(pasta)
    return sorted(p for p in pasta.glob("*") if p.is_file()
                  and re.search(padrao, p.name, re.I) and p.suffix.lower() in {".csv", ".xlsx", ".xls", ".txt"})


def extrair(pasta: Path) -> dict[str, list[pd.DataFrame]]:
    """Agrupa os arquivos por tipo, pelo nome: *pontos*, *massa*/*peso*, *popul*."""
    return {
        "pontos": [ler_tabela(p) for p in listar(pasta, r"ponto")],
        "massa": [ler_tabela(p) for p in listar(pasta, r"massa|peso|tonelad")],
        "populacao": [ler_tabela(p) for p in listar(pasta, r"popul")],
    }


PLANILHAS = {".xlsx", ".xls", ".csv", ".ods"}


def _ano_no_conteudo(caminho: Path) -> int | None:
    """Lê só o começo da planilha e devolve o valor mais comum da coluna "Ano" (ano da declaração)."""
    try:
        if caminho.suffix.lower() in {".xlsx", ".xls", ".ods"}:
            df = pd.read_excel(caminho, dtype=str, nrows=50)
        else:
            with open(caminho, "rb") as f:
                bruto = f.read(20000)
            texto = next((bruto.decode(e, errors="ignore") for e in ENCODINGS), "")
            texto = texto.rsplit("\n", 1)[0]  # descarta a última linha (pode estar cortada)
            try:
                sep = csv.Sniffer().sniff(texto[:5000], delimiters=";,\t|").delimiter
            except csv.Error:
                sep = ";" if texto.count(";") > texto.count(",") else ","
            df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, keep_default_na=False, on_bad_lines="skip")
    except Exception:  # noqa: BLE001
        return None
    col = next((c for c in df.columns if str(c).strip().lower() == "ano"), None)
    if col is None:
        return None
    anos = pd.to_numeric(df[col], errors="coerce").dropna().astype(int)
    anos = anos[(anos >= 2000) & (anos <= 2100)]
    return int(anos.mode().iloc[0]) if len(anos) else None


def planilhas_por_ano(pasta: Path, ano_min: int, ano_max: int) -> dict[int, list[Path]]:
    """Agrupa as planilhas extraídas por ano, seja qual for o nome das pastas.

    O ano vem, nesta ordem, da coluna "Ano" da própria planilha, de uma pasta com
    nome de ano (extraido/2024) ou do último ano que aparece no caminho
    (extraido/EstadosMunicipios2025/...). Assim não importa como o ZIP foi
    descompactado (o de 2024 do SINIR, por exemplo, traz uma pasta chamada 2023).
    """
    grupos: dict[int, list[Path]] = {}
    if not pasta.exists():
        return grupos
    vistos = set()
    for arq in sorted(pasta.rglob("*")):
        if not arq.is_file() or arq.suffix.lower() not in PLANILHAS or "__MACOSX" in arq.parts or arq.name.startswith("._"):
            continue
        ano = _ano_no_conteudo(arq)
        if ano is None:
            rel = arq.relative_to(pasta)
            pastas = [p for p in rel.parts[:-1] if p.isdigit()]
            achados = re.findall(r"20\d{2}", str(rel))
            ano = int(pastas[0]) if pastas else int(achados[-1]) if achados else None
        if ano is None or not ano_min <= ano <= ano_max:
            continue
        chave = (ano, arq.name, arq.stat().st_size)  # o mesmo arquivo extraído duas vezes conta uma só
        if chave in vistos:
            continue
        vistos.add(chave)
        grupos.setdefault(ano, []).append(arq)
    return dict(sorted(grupos.items()))
