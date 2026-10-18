"""Índice de prioridade para novos pontos de recebimento com dados do SINIR (2023–2025).

Os relatórios das entidades não trazem pontos por município depois de 2022, então o índice
combina o que existe para cada município-alvo do Decreto 10.240/2020 (aproximação: mais de
80 mil habitantes) em cada ano com planilhas do SINIR:

* demanda: posição do município nos pontos exigidos (população ÷ 25 mil), de 0 a 1;
* sinais de fragilidade (0 ou 1): sem PEV listado, sem plano declarado, plano sem REEE,
  sem coleta seletiva, plano sem ecoponto/PEV e passivo ambiental declarado.

Índice = 100 × Σ peso × componente (pesos em config.PESOS_PRIORIDADE_SINIR).
Quem não declarou o plano recebe também os sinais que dependem do plano: falta de
informação conta como sinal, para não ficar à frente de quem declarou.
"""
from __future__ import annotations

import math

import pandas as pd

from . import config as C

# Padrões usados quando o config.py não define os pesos (ex.: config local com outro recorte)
PESOS_PADRAO = {"demanda": 0.50, "sem_pev_listado": 0.15, "sem_plano": 0.10, "plano_sem_reee": 0.10,
                "sem_coleta_seletiva": 0.05, "plano_sem_pev": 0.05, "passivo": 0.05}
CLASSES_PADRAO = ((70, "Alta"), (55, "Média"), (0, "Baixa"))


def pesos() -> dict:
    return getattr(C, "PESOS_PRIORIDADE_SINIR", PESOS_PADRAO)


def classes() -> tuple:
    return getattr(C, "CLASSES_PRIORIDADE_SINIR", CLASSES_PADRAO)


SINAIS = ("sem_pev_listado", "sem_plano", "plano_sem_reee", "sem_coleta_seletiva", "plano_sem_pev", "passivo")
COLUNAS = ["cod_ibge", "ano", "municipio", "uf", "populacao", "pontos_exigidos", "pevs_listados",
           *SINAIS, "demanda", "indice_prioridade", "classe_prioridade"]


def _classe(v: float) -> str:
    for limite, nome in classes():
        if v >= limite:
            return nome
    return classes()[-1][1]


def calcular(mun: pd.DataFrame, planos: pd.DataFrame | None, extras_mun: pd.DataFrame | None = None,
             mun_entidade: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por município-alvo e ano com planilhas do SINIR (dentro do recorte de config)."""
    if planos is None or not len(planos):
        return pd.DataFrame(columns=COLUNAS)
    anos = sorted(a for a in planos["ano"].dropna().astype(int).unique() if a in C.ANOS)
    alvo = mun[mun["populacao"] > C.LIMIAR_POPULACIONAL][["cod_ibge", "municipio", "uf", "populacao"]].copy()
    if not anos or not len(alvo):
        return pd.DataFrame(columns=COLUNAS)
    alvo["pontos_exigidos"] = alvo["populacao"].map(lambda p: math.ceil(p / C.HAB_POR_PONTO_DECRETO))
    # posição na demanda (0 a 1): empates recebem a mesma posição
    alvo["demanda"] = alvo["pontos_exigidos"].rank(pct=True, method="max").round(4)
    pevs = (mun_entidade.groupby("cod_ibge")["pontos"].sum() if mun_entidade is not None and len(mun_entidade)
            else pd.Series(dtype=float))
    alvo["pevs_listados"] = alvo["cod_ibge"].map(pevs).fillna(0).astype(int)

    pl = planos.set_index(["cod_ibge", "ano"])
    ex = (extras_mun.set_index(["cod_ibge", "ano"])["passivo"]
          if extras_mun is not None and len(extras_mun) and "passivo" in extras_mun else pd.Series(dtype=float))
    linhas = []
    for ano in anos:
        for r in alvo.itertuples(index=False):
            p = pl.loc[(r.cod_ibge, ano)] if (r.cod_ibge, ano) in pl.index else None
            if isinstance(p, pd.DataFrame):  # duplicata eventual: usa a primeira declaração
                p = p.iloc[0]
            declarou = p is not None
            s = {
                "sem_pev_listado": int(r.pevs_listados == 0),
                "sem_plano": int(not declarou),
                "plano_sem_reee": int(not declarou or not bool(p["cita_reee"])),
                "sem_coleta_seletiva": int(not declarou or not (p.get("coleta_seletiva") == 1)),
                "plano_sem_pev": int(not declarou or not bool(p.get("cita_pev", False))),
                "passivo": int(ex.get((r.cod_ibge, ano), 0) == 1),
            }
            p_ = pesos()
            indice = 100 * (p_["demanda"] * r.demanda + sum(p_[k] * v for k, v in s.items()))
            linhas.append({"cod_ibge": int(r.cod_ibge), "ano": int(ano), "municipio": r.municipio, "uf": r.uf,
                           "populacao": int(r.populacao), "pontos_exigidos": int(r.pontos_exigidos),
                           "pevs_listados": int(r.pevs_listados), **s, "demanda": r.demanda,
                           "indice_prioridade": round(indice, 1), "classe_prioridade": _classe(indice)})
    df = pd.DataFrame(linhas, columns=COLUNAS)
    return df.sort_values(["ano", "indice_prioridade", "populacao"], ascending=[True, False, False]).reset_index(drop=True)
