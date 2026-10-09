"""Gerador de dados SINTÉTICOS no formato das exportações do SINIR.

Por que existe: o portal do SINIR e o IBGE nem sempre estão acessíveis (e o
layout dos arquivos muda de ano para ano). Para que o pipeline e o dashboard
possam ser desenvolvidos, testados e demonstrados, este módulo produz arquivos
"crus" que imitam os problemas reais dessas fontes:

* encoding latin-1 e separador ";" nos anos antigos, UTF-8 e "," nos novos;
* cabeçalhos com nomes diferentes entre anos;
* nomes de municípios em caixa alta, sem acento ou com espaços extras;
* código IBGE ausente em parte das linhas;
* registros duplicados e pontos inativos;
* massa em formato brasileiro ("1.234,56") e, em 2019–2020, só por UF (XLSX).

NADA aqui é dado real do SINIR. Os arquivos ficam em data/raw/demo/ e todos
os produtos derivados levam a marca fonte="demo".
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config as C

ENTIDADES = ["ABREE", "Green Eletron", "Sistema individual"]
P_ENTIDADES = [0.52, 0.40, 0.08]
TIPOS = ["PEV fixo", "Ponto de consolidação", "Campanha itinerante"]
P_TIPOS = [0.82, 0.10, 0.08]


def carregar_base_ibge() -> pd.DataFrame:
    mun = pd.read_csv(C.RAW_IBGE / "municipios_kelvins.csv")
    est = pd.read_csv(C.RAW_IBGE / "estados_kelvins.csv", encoding="utf-8-sig")
    mun = mun.merge(est[["codigo_uf", "uf", "regiao"]], on="codigo_uf", how="left")
    return mun[["codigo_ibge", "nome", "uf", "regiao", "latitude", "longitude", "capital"]]


def populacao_sintetica(mun: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Distribui a população do Censo 2022 de cada UF entre seus municípios.

    A capital recebe uma fatia de 15–35 % e os demais seguem pesos log-normais,
    o que reproduz a forte concentração urbana brasileira. Os totais por UF
    batem com o Censo; os valores municipais são fictícios.
    """
    partes = []
    for uf, g in mun.groupby("uf"):
        total = C.POP_UF_CENSO_2022[uf]
        g = g.copy()
        if len(g) == 1:
            g["populacao"] = total
        else:
            pesos = rng.lognormal(mean=0, sigma=1.1, size=len(g))
            cap = g["capital"].to_numpy() == 1
            fatia_cap = rng.uniform(0.15, 0.35)
            # nenhum município do interior passa de 4 % da UF nem de 900 mil hab.
            teto = min(0.04, 900_000 / total)
            for _ in range(5):
                pesos = pesos / pesos[~cap].sum() * (1 - fatia_cap)
                pesos = np.minimum(pesos, teto)
            pesos = pesos / pesos[~cap].sum() * (1 - fatia_cap)
            pesos[cap] = fatia_cap
            g["populacao"] = np.maximum(800, np.round(pesos * total)).astype(int)
        partes.append(g)
    return pd.concat(partes)


def _bagunca_nome(nome: str, rng: np.random.Generator) -> str:
    r = rng.random()
    if r < 0.25:
        return nome.upper()
    if r < 0.40:
        import unicodedata
        return "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
    if r < 0.48:
        return f"  {nome} "
    return nome


def simular_pontos(mun: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Gera a rede de pontos ano a ano (snapshot dos pontos ativos)."""
    linhas = []
    mun = mun.sort_values("populacao", ascending=False).reset_index(drop=True)
    for i, m in mun.iterrows():
        pop = m.populacao
        necessarios = math.ceil(pop / C.HAB_POR_PONTO_DECRETO)
        if pop > C.LIMIAR_POPULACIONAL:
            # maiores cidades aderem antes; ruído desloca a ordem
            base = 2019 + min(6, int(i / 70)) + rng.integers(-1, 2)
            adesao = int(np.clip(base, 2019, 2026))
            empenho = rng.uniform(0.35, 1.25)  # alguns nunca cumprem a meta
        else:
            adesao = 2019 + int(rng.exponential(9))
            empenho = 1.0
            necessarios = 1 if rng.random() > 0.15 else 2
        if adesao > C.ANO_FINAL:
            continue
        n_existentes = 0
        for ano in C.ANOS:
            if ano < adesao:
                continue
            maturidade = min(1.0, 0.3 + 0.2 * (ano - adesao))
            alvo = max(1, round(necessarios * maturidade * empenho))
            n_existentes = max(n_existentes, alvo)
            for k in range(n_existentes):
                linhas.append({
                    "id_ponto": f"{m.codigo_ibge}-{k:03d}",
                    "ano": ano,
                    "cod_ibge": m.codigo_ibge,
                    "municipio": m.nome,
                    "uf": m.uf,
                })
    pts = pd.DataFrame(linhas)
    ids = pts["id_ponto"].unique()
    atrib = pd.DataFrame({
        "id_ponto": ids,
        "entidade": rng.choice(ENTIDADES, size=len(ids), p=P_ENTIDADES),
        "tipo": rng.choice(TIPOS, size=len(ids), p=P_TIPOS),
    })
    primeiro = pts.groupby("id_ponto")["ano"].min().rename("ano_inicio")
    pts = pts.merge(atrib, on="id_ponto").merge(primeiro, on="id_ponto")
    return pts


def simular_massa(pts: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Toneladas recebidas por município/ano a partir do nº de pontos."""
    por_mun = pts.groupby(["ano", "cod_ibge", "municipio", "uf"]).size().rename("pontos").reset_index()
    fator_ano = {a: 0.30 + 0.06 * (a - C.ANO_INICIAL) for a in C.ANOS}  # t/ponto cresce
    por_mun["toneladas"] = [
        p * fator_ano[a] * rng.lognormal(0, 0.45) for p, a in zip(por_mun.pontos, por_mun.ano)
    ]
    return por_mun


def _fmt_br(x: float, casas: int = 3) -> str:
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def gerar(seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    C.RAW_DEMO.mkdir(parents=True, exist_ok=True)
    mun = populacao_sintetica(carregar_base_ibge(), rng)

    pop = mun[["codigo_ibge", "nome", "uf", "populacao"]].rename(
        columns={"codigo_ibge": "Cód. IBGE", "nome": "Município", "uf": "UF", "populacao": "População residente"})
    pop.to_csv(C.RAW_DEMO / "ibge_populacao_SINTETICA.csv", index=False, sep=";", encoding="utf-8")

    pts = simular_pontos(mun, rng)
    for ano, g in pts.groupby("ano"):
        g = g.copy()
        g["municipio"] = [_bagunca_nome(n, rng) for n in g["municipio"]]
        g.loc[rng.random(len(g)) < 0.015, "cod_ibge"] = np.nan  # código faltante
        g["situacao"] = np.where(rng.random(len(g)) < 0.02, "Inativo", "Ativo")
        g["data_cadastro"] = [f"{rng.integers(1, 29):02d}/{rng.integers(1, 13):02d}/{a}" for a in g["ano_inicio"]]
        dup = g.sample(frac=0.01, random_state=int(ano))
        g = pd.concat([g, dup]).sample(frac=1, random_state=int(ano))
        if ano <= 2021:
            out = g.rename(columns={"uf": "UF", "municipio": "Município", "cod_ibge": "Código IBGE",
                                    "entidade": "Entidade Gestora", "tipo": "Tipo de Ponto",
                                    "situacao": "Situação", "data_cadastro": "Data de Cadastro"})
            cols = ["id_ponto", "UF", "Município", "Código IBGE", "Entidade Gestora",
                    "Tipo de Ponto", "Situação", "Data de Cadastro"]
            out["Código IBGE"] = out["Código IBGE"].map(lambda v: "" if pd.isna(v) else str(int(v)))
            out[cols].to_csv(C.RAW_DEMO / f"sinir_pontos_recebimento_{ano}.csv",
                             index=False, sep=";", encoding="latin-1")
        else:
            out = g.rename(columns={"uf": "sigla_uf", "municipio": "nome_municipio", "cod_ibge": "geocodigo",
                                    "entidade": "sistema", "tipo": "modalidade",
                                    "situacao": "status", "data_cadastro": "inicio_operacao"})
            cols = ["id_ponto", "ano", "sigla_uf", "nome_municipio", "geocodigo", "sistema",
                    "modalidade", "status", "inicio_operacao"]
            out["geocodigo"] = out["geocodigo"].astype("Int64")
            out[cols].to_csv(C.RAW_DEMO / f"sinir_pontos_recebimento_{ano}.csv", index=False, encoding="utf-8")

    massa = simular_massa(pts, rng)
    # 2019–2020: só total por UF, em planilha
    uf = (massa[massa.ano <= 2020].groupby(["ano", "uf"])["toneladas"].sum().reset_index()
          .rename(columns={"ano": "Ano", "uf": "UF", "toneladas": "Peso recebido (t)"}))
    uf.to_excel(C.RAW_DEMO / "massa_reee_uf_2019_2020.xlsx", index=False)
    # 2021+: municipal, CSV com decimal brasileiro
    for ano, g in massa[massa.ano >= 2021].groupby("ano"):
        out = pd.DataFrame({
            "Ano": ano, "UF": g.uf, "Município": g.municipio, "Cód. IBGE": g.cod_ibge,
            "Peso recebido (t)": [_fmt_br(t) for t in g.toneladas],
        })
        out.to_csv(C.RAW_DEMO / f"massa_reee_municipal_{ano}.csv", index=False, sep=";", encoding="utf-8")

    (C.RAW_DEMO / "LEIA-ME.txt").write_text(
        "DADOS SINTÉTICOS gerados por src/reee/demo.py (seed=%d).\n"
        "Imitam o formato das exportações do SINIR, mas NÃO são dados reais.\n"
        "Para usar dados reais, coloque as exportações em data/raw/sinir/ e a\n"
        "população IBGE em data/raw/ibge/populacao.csv e rode sem --demo.\n" % seed,
        encoding="utf-8")


if __name__ == "__main__":
    gerar()
