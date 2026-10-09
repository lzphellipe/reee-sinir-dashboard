"""Etapa T (Transform): padronização, limpeza e georreferenciamento.

Saídas desta etapa (DataFrames "tidy"):
* dim_municipio – cadastro IBGE + população
* pontos        – um registro por ponto de recebimento ativo por ano
* massa_mun     – toneladas por município/ano (quando a fonte é municipal)
* massa_uf      – toneladas por UF/ano (quando a fonte só traz UF)
e um dicionário `qualidade` com o que foi corrigido ou descartado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .utils import chave_municipio, numero_br, padronizar_colunas


def dim_municipio(pop_raw: list[pd.DataFrame]) -> pd.DataFrame:
    mun = pd.read_csv(C.RAW_IBGE / "municipios_kelvins.csv")
    est = pd.read_csv(C.RAW_IBGE / "estados_kelvins.csv", encoding="utf-8-sig")
    mun = mun.merge(est[["codigo_uf", "uf", "nome", "regiao"]].rename(columns={"nome": "nome_uf"}),
                    on="codigo_uf", how="left")
    mun = mun.rename(columns={"codigo_ibge": "cod_ibge", "nome": "municipio",
                              "latitude": "lat", "longitude": "lon"})
    if not pop_raw:
        raise FileNotFoundError("Arquivo de população (IBGE) não encontrado: *popul*.csv")
    pop = padronizar_colunas(pd.concat(pop_raw, ignore_index=True), C.ALIASES_POP)
    pop["cod_ibge"] = pop["cod_ibge"].map(numero_br).astype("Int64")
    # código de 6 dígitos (sem DV) também é aceito
    seis = pop["cod_ibge"] < 1_000_000
    if seis.any():
        mapa6 = dict(zip(mun["cod_ibge"] // 10, mun["cod_ibge"]))
        pop.loc[seis, "cod_ibge"] = pop.loc[seis, "cod_ibge"].map(mapa6)
    pop["populacao"] = pop["populacao"].map(numero_br)
    pop = pop.dropna(subset=["cod_ibge", "populacao"]).drop_duplicates("cod_ibge", keep="last")
    mun = mun.merge(pop[["cod_ibge", "populacao"]], on="cod_ibge", how="left")
    mun["populacao"] = mun["populacao"].fillna(0).astype(int)
    mun["obrigado_decreto"] = mun["populacao"] > C.LIMIAR_POPULACIONAL
    mun["faixa_pop"] = pd.cut(mun["populacao"], [-1, 20_000, 80_000, 500_000, np.inf],
                              labels=["até 20 mil", "20–80 mil", "80–500 mil", "acima de 500 mil"])
    mun["chave"] = [chave_municipio(n, u) for n, u in zip(mun.municipio, mun.uf)]
    return mun[["cod_ibge", "municipio", "uf", "nome_uf", "regiao", "lat", "lon", "capital",
                "populacao", "obrigado_decreto", "faixa_pop", "chave"]]


def _resolver_codigo(df: pd.DataFrame, mun: pd.DataFrame, q: dict, etapa: str) -> pd.DataFrame:
    """Preenche cod_ibge ausente pela chave nome+UF; descarta o que não casar."""
    df = df.copy()
    df["cod_ibge"] = df.get("cod_ibge", pd.Series(index=df.index, dtype=str)).map(numero_br).astype("Int64")
    validos = set(mun["cod_ibge"])
    df.loc[~df["cod_ibge"].isin(validos), "cod_ibge"] = pd.NA
    faltando = df["cod_ibge"].isna()
    if faltando.any() and {"municipio", "uf"} <= set(df.columns):
        mapa = dict(zip(mun["chave"], mun["cod_ibge"]))
        chaves = [chave_municipio(n, u) for n, u in zip(df.loc[faltando, "municipio"], df.loc[faltando, "uf"])]
        df.loc[faltando, "cod_ibge"] = pd.array([mapa.get(k) for k in chaves], dtype="Int64")
    recuperados = int(faltando.sum() - df["cod_ibge"].isna().sum())
    perdidos = df[df["cod_ibge"].isna()]
    q[f"{etapa}_codigo_recuperado_por_nome"] = recuperados
    q[f"{etapa}_sem_municipio_descartados"] = int(len(perdidos))
    if len(perdidos):
        q[f"{etapa}_exemplos_nao_casados"] = (perdidos.get("municipio", pd.Series(dtype=str)).astype(str)
                                              + "/" + perdidos.get("uf", pd.Series(dtype=str)).astype(str)
                                              ).head(10).tolist()
    return df.dropna(subset=["cod_ibge"])


def limpar_pontos(raw: list[pd.DataFrame], mun: pd.DataFrame, q: dict) -> pd.DataFrame:
    if not raw:
        raise FileNotFoundError("Nenhum arquivo de pontos de recebimento (*ponto*) encontrado")
    partes = [padronizar_colunas(df, C.ALIASES_PONTOS) for df in raw]
    df = pd.concat(partes, ignore_index=True)
    q["pontos_linhas_lidas"] = int(len(df))

    if "ano" in df.columns:
        df["ano"] = pd.to_numeric(df["ano"], errors="coerce").fillna(df["_ano_arquivo"])
    else:
        df["ano"] = df["_ano_arquivo"]
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    fora = ~df["ano"].between(C.ANO_INICIAL, C.ANO_FINAL)
    q["pontos_fora_do_periodo"] = int(fora.sum())
    df = df[~fora]

    df["uf"] = df["uf"].astype(str).str.strip().str.upper()
    df["municipio"] = df["municipio"].astype(str).str.strip()
    if "situacao" in df.columns:
        inativo = df["situacao"].astype(str).str.lower().str.contains("inativ|desativ|encerr")
        q["pontos_inativos_removidos"] = int(inativo.sum())
        df = df[~inativo]

    df = _resolver_codigo(df, mun, q, "pontos")

    chave_dup = ["id_ponto", "ano"] if "id_ponto" in df.columns else \
        ["cod_ibge", "entidade", "tipo", "data_cadastro", "ano"]
    antes = len(df)
    df = df.drop_duplicates(subset=[c for c in chave_dup if c in df.columns])
    q["pontos_duplicados_removidos"] = int(antes - len(df))

    for col, padrao in {"entidade": "Não informado", "tipo": "Não informado"}.items():
        if col not in df.columns:
            df[col] = padrao
        df[col] = df[col].replace("", padrao).fillna(padrao).astype(str).str.strip()
    q["pontos_registros_validos"] = int(len(df))
    cols = ["ano", "cod_ibge", "entidade", "tipo"] + (["id_ponto"] if "id_ponto" in df.columns else [])
    return df[cols].reset_index(drop=True)


def limpar_massa(raw: list[pd.DataFrame], mun: pd.DataFrame, q: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    vazio_mun = pd.DataFrame(columns=["ano", "cod_ibge", "toneladas"])
    vazio_uf = pd.DataFrame(columns=["ano", "uf", "toneladas"])
    if not raw:
        q["massa_aviso"] = "nenhum arquivo de massa encontrado"
        return vazio_mun, vazio_uf
    df = pd.concat([padronizar_colunas(d, C.ALIASES_MASSA) for d in raw], ignore_index=True)
    q["massa_linhas_lidas"] = int(len(df))
    if "ano" not in df.columns:
        df["ano"] = df["_ano_arquivo"]
    df["ano"] = pd.to_numeric(df["ano"].replace("", np.nan), errors="coerce").fillna(df["_ano_arquivo"]).astype("Int64")
    if "toneladas" in df.columns:
        df["toneladas"] = df["toneladas"].map(numero_br)
    else:
        df["toneladas"] = np.nan
    if "kg" in df.columns:
        df["toneladas"] = df["toneladas"].fillna(df["kg"].map(numero_br) / 1000)
    invalida = df["toneladas"].isna() | (df["toneladas"] < 0)
    q["massa_valores_invalidos"] = int(invalida.sum())
    df = df[~invalida & df["ano"].between(C.ANO_INICIAL, C.ANO_FINAL)]
    df["uf"] = df["uf"].astype(str).str.strip().str.upper()

    tem_mun = df.get("municipio", pd.Series("", index=df.index)).fillna("").astype(str).str.strip() != ""
    if "cod_ibge" in df.columns:
        tem_mun |= df["cod_ibge"].fillna("").astype(str).str.strip() != ""
    municipal = _resolver_codigo(df[tem_mun], mun, q, "massa") if tem_mun.any() else vazio_mun
    massa_mun = (municipal.groupby(["ano", "cod_ibge"], as_index=False)["toneladas"].sum()
                 if len(municipal) else vazio_mun)
    massa_uf = df[~tem_mun].groupby(["ano", "uf"], as_index=False)["toneladas"].sum()

    # outliers: t/ano muito acima do esperado para o porte -> só sinaliza
    if len(massa_mun):
        z = massa_mun.groupby("ano")["toneladas"].transform(lambda s: (s - s.median()) / (s.std() or 1))
        q["massa_outliers_sinalizados"] = int((z > 6).sum())
    return massa_mun, massa_uf
