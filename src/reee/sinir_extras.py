"""Outros dados municipais do SINIR úteis ao painel: custos do manejo e passivos ambientais.

* "Municipal - Soluções Compartilhadas e Custos": custo anual (R$) da coleta
  convencional, da coleta seletiva e da disposição final, e se há taxa de cobrança.
  O custo vira R$ por habitante por ano (população do Censo 2022). Valores acima de
  R$ 1.000/hab./ano são tratados como erro de digitação e descartados.
* "Municipal - Passivo Ambiental": se o município declara passivo (lixão antigo,
  área degradada) e quantos registros declarou. O arquivo não traz coordenadas
  preenchidas; o mapa usa a sede do município.

Mesma regra das outras etapas: quem não declarou fica sem informação (nulo).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .extract import ler_tabela, planilhas_por_ano
from .utils import normalizar_texto, numero_br

LIMITE_RS_HAB = 1000.0
COLUNAS = ["cod_ibge", "ano", "custo_conv", "custo_sel", "custo_disp", "taxa", "passivo", "n_passivos"]


def _col(df, alvo):
    return next((c for c in df.columns if normalizar_texto(c) == alvo), None)


def _sim(v) -> float:
    t = normalizar_texto(v)
    return 1.0 if t in ("sim", "s") else 0.0 if t in ("nao", "n") else np.nan


def processar(mun: pd.DataFrame, q: dict, pasta: Path | None = None) -> pd.DataFrame:
    from .planos_sinir import _casar, _limpa_nome, _uf_sigla
    pasta = pasta or (C.RAW_SINIR / "extraido")
    partes = []
    for ano, arquivos in planilhas_por_ano(pasta, C.ANO_INICIAL, C.ANO_FINAL).items():
        for arq in arquivos:
            nome = normalizar_texto(arq.name)
            tipo = "custo" if "solucoes compartilhadas" in nome else "passivo" if "passivo ambiental" in nome else None
            if not tipo or "municipal" not in nome:
                continue
            try:
                df = ler_tabela(arq)
            except Exception as e:  # noqa: BLE001
                q.setdefault("extras_arquivos_com_erro", []).append(f"{arq.name}: {e}")
                continue
            cm, cu = _col(df, "municipio declarante"), _col(df, "uf declarante")
            if not cm or not cu:
                continue
            df = df.assign(_mun=df[cm].map(_limpa_nome), _uf=df[cu].map(_uf_sigla))
            df = df[(df["_mun"].str.len() > 0) & (df["_mun"].map(normalizar_texto) != normalizar_texto(cm))]
            if df.empty:
                continue
            df["cod_ibge"] = _casar(df, mun, {})
            df = df.dropna(subset=["cod_ibge"]).assign(ano=ano)
            out = pd.DataFrame({"cod_ibge": df["cod_ibge"].astype(int), "ano": ano})
            if tipo == "custo":
                for campo, alvo in (("custo_conv", "custo coleta convencional"), ("custo_sel", "custo coleta seletiva"),
                                    ("custo_disp", "custo disposicao final")):
                    c = _col(df, alvo)
                    out[campo] = df[c].map(numero_br).values if c else np.nan
                c = _col(df, "possui taxa de cobranca")
                out["taxa"] = df[c].map(_sim).values if c else np.nan
            else:
                c, d = _col(df, "possui passivo ambiental"), _col(df, "passivo ambiental descritivo")
                out["passivo"] = df[c].map(_sim).values if c else np.nan
                out["n_passivos"] = ((df[c].map(_sim) == 1) & (df[d].astype(str).str.strip() != "")).astype(float).values if c and d else np.nan
            partes.append(out)
    if not partes:
        return pd.DataFrame(columns=COLUNAS)
    tudo = pd.concat(partes, ignore_index=True)
    for c in COLUNAS[2:]:
        if c not in tudo:
            tudo[c] = np.nan
    agg = tudo.groupby(["cod_ibge", "ano"], as_index=False).agg(
        custo_conv=("custo_conv", "max"), custo_sel=("custo_sel", "max"), custo_disp=("custo_disp", "max"),
        taxa=("taxa", "max"), passivo=("passivo", "max"), n_passivos=("n_passivos", lambda s: s.sum(min_count=1)))
    pop = mun.set_index("cod_ibge")["populacao"]
    for c in ("custo_conv", "custo_sel", "custo_disp"):
        hab = agg[c] / agg["cod_ibge"].map(pop)
        ruim = (hab > LIMITE_RS_HAB) | (agg[c] <= 0)
        q[f"{c}_descartados"] = int(ruim.sum())
        agg[f"{c}_hab"] = hab.where(~ruim).round(2)
    agg.loc[(agg["passivo"] == 1) & (agg["n_passivos"].fillna(0) == 0), "n_passivos"] = 1.0
    q["extras_municipio_ano"] = int(len(agg))
    return agg


def agregar(df: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    """Medianas de custo por habitante, % com taxa e municípios com passivo."""
    if df.empty:
        return pd.DataFrame(columns=[*chave])
    g = df.groupby(chave)
    a = pd.DataFrame({
        "custo_conv_hab": g["custo_conv_hab"].median(),
        "custo_sel_hab": g["custo_sel_hab"].median(),
        "custo_disp_hab": g["custo_disp_hab"].median(),
        "municipios_custo": g["custo_conv_hab"].count(),
        "pct_taxa": (g["taxa"].sum(min_count=1) / g["taxa"].count() * 100),
        "municipios_passivo": g["passivo"].sum(min_count=1),
        "pct_passivo": (g["passivo"].sum(min_count=1) / g["passivo"].count() * 100),
        "passivos": g["n_passivos"].sum(min_count=1),
    }).round(1).reset_index()
    return a
