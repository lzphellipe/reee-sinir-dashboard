"""Dados dos relatórios anuais das entidades gestoras publicados no SINIR.

Os relatórios de resultados (ABREE, Green Eletron) são PDFs. As tabelas foram
transcritas para CSV em data/raw/sinir/relatorios/ e conferidas contra os
totais impressos em cada documento (ver fontes.json). Este módulo:

* lê as tabelas por UF e a lista municipal disponível;
* casa nomes de municípios com o cadastro IBGE, tolerando erros de grafia
  do documento ("Cascável", "Guarupuava", "Poços de Calda"...);
* devolve tabelas por UF/ano/entidade, por entidade/ano e por município.

Limites conhecidos (aparecem no painel):
* ABREE não publica a lista de municípios atendidos, só a contagem por UF;
* "municípios atendidos" pode somar o mesmo município duas vezes quando as
  duas entidades atuam nele;
* não há relatório publicado para 2019–2020 (só totais citados pela ABREE)
  nem para 2024–2025 no portal do SINIR na data da coleta.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .utils import chave_municipio, normalizar_texto, numero_br

def _pasta() -> Path:
    return C.RAW_SINIR / "relatorios"  # resolvido na hora: respeita mudanças na configuração


def disponivel(pasta: Path | None = None) -> bool:
    return (pasta or _pasta()).joinpath("totais_nacionais.csv").exists()


def _casar_municipios(df: pd.DataFrame, mun: pd.DataFrame, q: dict) -> pd.DataFrame:
    chave = dict(zip(mun["chave"], mun["cod_ibge"]))
    por_uf = {uf: g for uf, g in mun.groupby("uf")}
    cods, metodo = [], []
    corrigidos = []
    for nome, uf in zip(df["municipio"], df["uf"]):
        k = chave_municipio(nome, uf)
        if k in chave:
            cods.append(chave[k]); metodo.append("exato"); continue
        cand = por_uf[uf]
        nomes = [normalizar_texto(n) for n in cand["municipio"]]
        alvo = normalizar_texto(nome)
        # 1) nome do documento é prefixo do oficial ("Águas Lindas" -> "Águas Lindas de Goiás")
        pref = [i for i, n in enumerate(nomes) if n.startswith(alvo + " ")]
        # 2) semelhança de grafia
        prox = difflib.get_close_matches(alvo, nomes, n=1, cutoff=0.85)
        if len(pref) == 1:
            i = pref[0]
        elif prox:
            i = nomes.index(prox[0])
        else:
            cods.append(pd.NA); metodo.append("não casado"); continue
        cods.append(int(cand["cod_ibge"].iloc[i])); metodo.append("aproximado")
        corrigidos.append(f"{nome}/{uf} → {cand['municipio'].iloc[i]}")
    df = df.assign(cod_ibge=pd.array(cods, dtype="Int64"), casamento=metodo)
    q["relatorio_municipios_nome_corrigido"] = corrigidos
    q["relatorio_municipios_nao_casados"] = df.loc[df["cod_ibge"].isna(), "municipio"].tolist()
    return df


def carregar(mun: pd.DataFrame, q: dict, pasta: Path | None = None) -> dict:
    p = pasta or _pasta()
    nac = pd.read_csv(p / "totais_nacionais.csv", dtype=str)
    for c in ("pontos", "municipios_atendidos", "toneladas"):
        nac[c] = nac[c].map(numero_br)
    nac["ano"] = nac["ano"].astype(int)

    linhas = []
    abree = pd.read_csv(p / "abree_2022_uf.csv", dtype=str)
    for _, r in abree.iterrows():
        linhas.append({"ano": 2021, "uf": r.uf, "entidade": "ABREE", "pontos": numero_br(r.pontos_2021),
                       "municipios_atendidos": np.nan, "toneladas": np.nan})
        linhas.append({"ano": 2022, "uf": r.uf, "entidade": "ABREE", "pontos": numero_br(r.pontos_2022),
                       "municipios_atendidos": numero_br(r.municipios_atendidos_2022),
                       "toneladas": numero_br(r.toneladas_2022)})
    g23 = pd.read_csv(p / "green_2023_uf.csv")
    for _, r in g23.iterrows():
        linhas.append({"ano": 2023, "uf": r.uf, "entidade": "Green Eletron", "pontos": float(r.pevs_2023),
                       "municipios_atendidos": float(r.municipios_atendidos_2023), "toneladas": np.nan})

    gm = _casar_municipios(pd.read_csv(p / "green_2022_municipios.csv"), mun, q)
    gm_ok = gm.dropna(subset=["cod_ibge"])
    for uf, s in gm.groupby("uf"):
        linhas.append({"ano": 2022, "uf": uf, "entidade": "Green Eletron", "pontos": float(s["pevs"].sum()),
                       "municipios_atendidos": float(len(s)), "toneladas": np.nan})
    uf_ent = pd.DataFrame(linhas)

    # validação: somas por UF batem com os totais nacionais impressos
    for (ano, ent), s in uf_ent.groupby(["ano", "entidade"]):
        tot = nac[(nac.ano == ano) & (nac.entidade == ent)]
        if len(tot) and pd.notna(tot["pontos"].iloc[0]):
            if abs(s["pontos"].sum() - tot["pontos"].iloc[0]) > 0.5:
                raise ValueError(f"{ent} {ano}: soma por UF ({s['pontos'].sum()}) ≠ total impresso ({tot['pontos'].iloc[0]})")
    q["relatorios_validados"] = "somas por UF conferem com os totais impressos"

    mun_ent = (gm_ok.assign(ano=2022, entidade="Green Eletron")
               [["cod_ibge", "ano", "entidade", "pevs"]].rename(columns={"pevs": "pontos"}))
    fontes = json.loads((p / "fontes.json").read_text(encoding="utf-8")) if (p / "fontes.json").exists() else {}
    return {"nacional": nac, "uf_entidade": uf_ent, "mun_entidade": mun_ent, "fontes": fontes}


def aplicar(fuf: pd.DataFrame, fbr: pd.DataFrame, fmun: pd.DataFrame, rel: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Substitui pontos/toneladas por UF e Brasil pelos valores dos relatórios."""
    exig = (fmun[fmun["obrigado_decreto"]].groupby(["uf", "ano"])["pontos_necessarios"].sum()
            .rename("pontos_exigidos").reset_index())
    ue = rel["uf_entidade"]
    soma = (ue.groupby(["uf", "ano"]).agg(
        pontos=("pontos", lambda s: s.sum(min_count=1)),
        municipios_atendidos=("municipios_atendidos", lambda s: s.sum(min_count=1)),
        toneladas=("toneladas", lambda s: s.sum(min_count=1)),
        entidades=("entidade", lambda s: ", ".join(sorted(set(s))))).reset_index())
    fuf = (fuf.drop(columns=["pontos", "toneladas"], errors="ignore")
           .merge(soma, on=["uf", "ano"], how="left").merge(exig, on=["uf", "ano"], how="left"))
    fuf["fonte_massa"] = np.where(fuf["toneladas"].notna(), "relatório (ABREE, por UF)", "sem dado")

    nac = rel["nacional"].groupby("ano").agg(
        pontos=("pontos", lambda s: s.sum(min_count=1)),
        municipios_atendidos=("municipios_atendidos", lambda s: s.sum(min_count=1)),
        toneladas=("toneladas", lambda s: s.sum(min_count=1)),
        entidades=("entidade", lambda s: ", ".join(sorted(set(s))))).reset_index()
    exig_br = exig.groupby("ano")["pontos_exigidos"].sum().reset_index()
    fbr = (fbr.drop(columns=["pontos", "toneladas"], errors="ignore")
           .merge(nac, on="ano", how="left").merge(exig_br, on="ano", how="left"))
    for a in (fuf, fbr):
        a["pontos_100k"] = (a["pontos"] / a["populacao"] * 100_000).round(3)
        a["kg_hab"] = (a["toneladas"] * 1000 / a["populacao"]).round(4)
        a["cobertura_nominal"] = (a["pontos"] / a["pontos_exigidos"] * 100).round(1)
        a["deficit_nominal"] = (a["pontos_exigidos"] - a["pontos"]).clip(lower=0)
        a.loc[a["pontos"].isna(), "deficit_nominal"] = np.nan
    return fuf, fbr
