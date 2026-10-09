"""Funções utilitárias de limpeza textual e numérica (padrão brasileiro)."""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd


def normalizar_texto(valor) -> str:
    """Minúsculas, sem acentos, sem pontuação e com espaços colapsados.

    >>> normalizar_texto("  São  Sebastião do PARAÍSO ")
    'sao sebastiao do paraiso'
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-zA-Z0-9 ]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def chave_municipio(nome, uf) -> str:
    """Chave de junção nome+UF, tolerante a grafias (ex.: "D'Oeste", "d Oeste")."""
    n = normalizar_texto(nome).replace(" ", "")
    return f"{n}|{str(uf).strip().upper()}"


def numero_br(valor) -> float:
    """Converte números em formato brasileiro ("1.234,56", "12,5 t") para float.

    Aceita também formato já numérico ou com ponto decimal ("1234.56").
    Retorna NaN quando não houver número.
    """
    if valor is None:
        return np.nan
    if isinstance(valor, (int, float, np.integer, np.floating)):
        return float(valor)
    s = str(valor).strip()
    if not s or s.lower() in {"-", "nan", "nd", "n/d", "sem informacao"}:
        return np.nan
    s = re.sub(r"[^0-9,.\-]", "", s)
    if "," in s:  # vírgula é decimal -> pontos são milhar
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:  # "1.234.567" sem decimal
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def padronizar_colunas(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    """Renomeia colunas para nomes canônicos usando a tabela de apelidos."""
    mapa = {}
    normalizadas = {col: normalizar_texto(col) for col in df.columns}
    for canonico, opcoes in aliases.items():
        opcoes_n = {normalizar_texto(o) for o in opcoes} | {canonico}
        for col, col_n in normalizadas.items():
            if col not in mapa and col_n in opcoes_n:
                mapa[col] = canonico
                break
    return df.rename(columns=mapa)


def minmax(serie: pd.Series) -> pd.Series:
    """Normaliza para 0–1; série constante vira 0."""
    s = serie.astype(float)
    amp = s.max() - s.min()
    if not np.isfinite(amp) or amp == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.min()) / amp
