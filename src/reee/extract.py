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
