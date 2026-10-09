"""Indicadores de monitoramento da logística reversa de REEE.

Definições (também documentadas em docs/metodologia.md):

* pontos               – pontos de recebimento ativos no ano
* pontos_necessarios   – ceil(pop / 25.000) se pop > 80.000 (Decreto 10.240/2020), senão 0
* deficit_pontos       – max(0, necessários − existentes)
* com_ponto            – município tem ao menos 1 ponto
* cumpre_densidade     – município obrigado com pontos ≥ necessários
* hab_por_ponto        – população / pontos
* kg_hab               – toneladas × 1000 / população
* indice_prioridade    – 0–100, combina déficit, população descoberta,
                         coleta per capita abaixo da UF e ausência de ponto
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .utils import minmax


def fato_municipio_ano(mun: pd.DataFrame, pontos_mun: pd.DataFrame, massa_mun: pd.DataFrame,
                       declaracoes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Grade município × ano com os indicadores.

    pontos_mun  – (cod_ibge, ano, pontos) já agregado, usado no modo cadastro de pontos
    declaracoes – (cod_ibge, ano, pontos, toneladas, possui) do módulo Estados e
                  Municípios do SINIR. Quando informado, município que não declarou
                  fica SEM INFORMAÇÃO (NaN), e não com zero pontos.
    """
    grade = pd.MultiIndex.from_product([mun["cod_ibge"], C.ANOS], names=["cod_ibge", "ano"]).to_frame(index=False)
    modo_declaratorio = declaracoes is not None
    if modo_declaratorio:
        d = declaracoes.copy()
        d["cod_ibge"], d["ano"] = d["cod_ibge"].astype(int), d["ano"].astype(int)
        f = grade.merge(d, on=["cod_ibge", "ano"], how="left", indicator=True)
        f["declarou"] = f.pop("_merge") == "both"
        f["pontos_estimado"] = f["pontos"].isna() & (f["possui"] == 1)
        f.loc[f["pontos"].isna() & (f["possui"] == 0), "pontos"] = 0
        f.loc[f["pontos_estimado"], "pontos"] = 1  # declarou que tem, sem informar quantos
        f = f.drop(columns=["possui"])
    else:
        cont = pontos_mun.copy()
        cont["cod_ibge"], cont["ano"] = cont["cod_ibge"].astype(int), cont["ano"].astype(int)
        f = grade.merge(cont, on=["cod_ibge", "ano"], how="left").fillna({"pontos": 0})
        f["declarou"] = True
        f["pontos_estimado"] = False
        anos_massa_mun = set()
        if len(massa_mun):
            mm = massa_mun.copy()
            mm["cod_ibge"], mm["ano"] = mm["cod_ibge"].astype(int), mm["ano"].astype(int)
            anos_massa_mun = set(mm["ano"].unique())
            f = f.merge(mm, on=["cod_ibge", "ano"], how="left")
        else:
            f["toneladas"] = np.nan
        # Em anos com fonte municipal, município sem ponto e sem registro = 0 t
        sem_registro = f["toneladas"].isna() & f["ano"].isin(anos_massa_mun) & (f["pontos"] == 0)
        f.loc[sem_registro, "toneladas"] = 0.0

    f = f.merge(mun[["cod_ibge", "uf", "populacao", "obrigado_decreto"]], on="cod_ibge", how="left")
    pop = f["populacao"].replace(0, np.nan)
    f["tem_info"] = f["pontos"].notna()
    f["pontos_necessarios"] = np.where(f["obrigado_decreto"], np.ceil(f["populacao"] / C.HAB_POR_PONTO_DECRETO), 0).astype(int)
    f["deficit_pontos"] = (f["pontos_necessarios"] - f["pontos"]).clip(lower=0)  # NaN se sem informação
    f.loc[~f["obrigado_decreto"], "deficit_pontos"] = 0
    f["com_ponto"] = f["pontos"].fillna(0) > 0
    f["cumpre_densidade"] = f["obrigado_decreto"] & (f["pontos"].fillna(-1) >= f["pontos_necessarios"])
    f["hab_por_ponto"] = (f["populacao"] / f["pontos"].replace(0, np.nan)).round(0)
    f["kg_hab"] = (f["toneladas"] * 1000 / pop).round(4)
    f["pontos_100k"] = (f["pontos"] / pop * 100_000).round(2)
    return f


def _agrega(f: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    g = f.assign(
        pop_com_ponto=np.where(f["com_ponto"], f["populacao"], 0),
        obrig_com_ponto=f["obrigado_decreto"] & f["com_ponto"],
        obrig_sem_info=f["obrigado_decreto"] & ~f["tem_info"],
    ).groupby(chaves)
    a = g.agg(
        pontos=("pontos", lambda s: s.sum(min_count=1)),
        declarantes=("declarou", "sum"),
        municipios_com_info=("tem_info", "sum"),
        obrigados_sem_info=("obrig_sem_info", "sum"),
        toneladas_mun=("toneladas", lambda s: s.sum(min_count=1)),
        populacao=("populacao", "sum"),
        pop_com_ponto=("pop_com_ponto", "sum"),
        municipios=("cod_ibge", "count"),
        municipios_com_ponto=("com_ponto", "sum"),
        obrigados=("obrigado_decreto", "sum"),
        obrigados_com_ponto=("obrig_com_ponto", "sum"),
        obrigados_cumprem=("cumpre_densidade", "sum"),
        deficit_pontos=("deficit_pontos", lambda s: s.sum(min_count=1)),
    ).reset_index()
    return a


def fato_uf_ano(f: pd.DataFrame, massa_uf: pd.DataFrame) -> pd.DataFrame:
    a = _agrega(f, ["uf", "ano"])
    if len(massa_uf):
        mu = massa_uf.copy()
        mu["ano"] = mu["ano"].astype(int)
        a = a.merge(mu.rename(columns={"toneladas": "toneladas_uf"}), on=["uf", "ano"], how="left")
        a["toneladas"] = a["toneladas_mun"].fillna(a["toneladas_uf"])
        a = a.drop(columns=["toneladas_uf"])
    else:
        a["toneladas"] = a["toneladas_mun"]
    a["fonte_massa"] = np.where(a["toneladas_mun"].notna(), "municipal",
                                np.where(a["toneladas"].notna(), "uf", "sem dado"))
    return _derivados(a.drop(columns=["toneladas_mun"]))


def fato_brasil_ano(uf_ano: pd.DataFrame) -> pd.DataFrame:
    cols = ["pontos", "toneladas", "populacao", "pop_com_ponto", "municipios", "municipios_com_ponto",
            "declarantes", "municipios_com_info", "obrigados_sem_info",
            "obrigados", "obrigados_com_ponto", "obrigados_cumprem", "deficit_pontos"]
    b = uf_ano.groupby("ano")[cols].sum(min_count=1).reset_index()
    b["meta_municipios"] = b["ano"].map(lambda a: C.METAS_DECRETO.get(a, {}).get("municipios"))
    b["meta_percentual_peso"] = b["ano"].map(lambda a: C.METAS_DECRETO.get(a, {}).get("percentual_peso"))
    return _derivados(b)


def _derivados(a: pd.DataFrame) -> pd.DataFrame:
    a["pct_municipios_com_info"] = (a["municipios_com_info"] / a["municipios"] * 100).round(2)
    a["pct_pop_coberta"] = (a["pop_com_ponto"] / a["populacao"] * 100).round(2)
    a["pct_obrigados_com_ponto"] = (a["obrigados_com_ponto"] / a["obrigados"].replace(0, np.nan) * 100).round(2)
    a["pontos_100k"] = (a["pontos"] / a["populacao"] * 100_000).round(3)
    a["kg_hab"] = (a["toneladas"] * 1000 / a["populacao"]).round(4)
    return a


def prioridade(f: pd.DataFrame, mun: pd.DataFrame, ano: int | None = None) -> pd.DataFrame:
    """Ranking de municípios para instalação de novos pontos (ano mais recente)."""
    com_info = f.loc[f["tem_info"], "ano"]
    ano = ano or int(com_info.max() if len(com_info) else f["ano"].max())  # ano mais recente com dados
    x = f[f["ano"] == ano].merge(mun[["cod_ibge", "municipio"]], on="cod_ibge")
    x = x[x["tem_info"]]  # só quem tem informação entra no ranking
    candidatos = x[(x["obrigado_decreto"] & (x["deficit_pontos"] > 0))
                   | ((x["populacao"] >= 20_000) & (x["pontos"] == 0))].copy()
    mediana_uf = x[x["kg_hab"] > 0].groupby("uf")["kg_hab"].median()
    med = candidatos["uf"].map(mediana_uf)
    gap = ((med - candidatos["kg_hab"].fillna(0)) / med).clip(0, 1).fillna(0.5)
    pop_desc = (candidatos["populacao"] - candidatos["pontos"] * C.HAB_POR_PONTO_DECRETO).clip(lower=0)
    P = C.PESOS_PRIORIDADE
    candidatos["indice_prioridade"] = (100 * (
        P["deficit"] * minmax(np.log1p(candidatos["deficit_pontos"]))
        + P["pop_descoberta"] * minmax(np.log1p(pop_desc))
        + P["baixa_coleta"] * gap
        + P["sem_ponto"] * (candidatos["pontos"] == 0)
    )).round(1)
    # classes relativas: 20 % mais altos = Alta, 40 % seguintes = Média
    rank = candidatos["indice_prioridade"].rank(pct=True, method="first")
    candidatos["classe_prioridade"] = pd.cut(rank, [0, 0.4, 0.8, 1.0], labels=["Baixa", "Média", "Alta"])
    return candidatos.sort_values("indice_prioridade", ascending=False).reset_index(drop=True)
