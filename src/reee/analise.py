"""Análise quantitativa exploratória (TCC, seção 3.6).

Relação entre a oferta de pontos de recebimento e a coleta, por UF:
correlação de Pearson, correlação de Spearman (postos) e regressão linear
simples (mínimos quadrados) de kg/hab. sobre pontos por 100 mil habitantes.

Usa o ano com mais UFs que têm os dois indicadores. Nos relatórios publicados,
só 2022 (ABREE) traz pontos e massa por estado; o painel deixa isso explícito.
Com 27 observações e um único ano, o resultado é descritivo: não permite
inferir causa nem generalizar para outros anos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pontos_x_coleta(fuf: pd.DataFrame, x: str = "pontos_100k", y: str = "kg_hab") -> dict | None:
    if x not in fuf or y not in fuf:
        return None
    base = fuf.dropna(subset=[x, y])
    base = base[(base[x] > 0) & (base[y] > 0)]
    if base.empty:
        return None
    ano = int(base.groupby("ano").size().idxmax())
    d = base[base["ano"] == ano]
    if len(d) < 5:
        return None
    pearson = float(d[x].corr(d[y]))
    spearman = float(d[x].rank().corr(d[y].rank()))
    b, a = np.polyfit(d[x], d[y], 1)  # y = a + b·x
    pred = a + b * d[x]
    r2 = float(1 - ((d[y] - pred) ** 2).sum() / ((d[y] - d[y].mean()) ** 2).sum())
    entidades = ", ".join(sorted({e for s in d.get("entidades", pd.Series(dtype=str)).dropna() for e in s.split(", ")}))
    return {
        "ano": ano, "n": int(len(d)), "x": x, "y": y, "entidades": entidades,
        "pearson": round(pearson, 3), "spearman": round(spearman, 3),
        "intercepto": round(float(a), 4), "inclinacao": round(float(b), 4), "r2": round(r2, 3),
        "pontos": [{"uf": r.uf, "x": round(float(getattr(r, x)), 3), "y": round(float(getattr(r, y)), 4)}
                   for r in d.itertuples()],
    }
