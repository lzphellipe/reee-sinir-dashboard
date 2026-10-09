"""Etapa L (Load): grava os produtos do pipeline.

* data/processed/*.csv           – tabelas tratadas (dados abertos)
* data/processed/powerbi/*.csv   – modelo estrela para Power BI
* dashboard/data/dashboard.json  – pacote compacto lido pelo dashboard web
* dashboard/data/uf.geojson      – malha das UFs simplificada
* data/processed/qualidade.json  – relatório de qualidade dos dados
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config as C


def _limpo(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 4)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is pd.NA:
        return None
    return v


def _registros(df: pd.DataFrame) -> list[dict]:
    return [{k: _limpo(v) for k, v in r.items()} for r in df.to_dict("records")]


def simplificar_geojson(origem, destino, casas: int = 2) -> None:
    """Arredonda coordenadas e remove vértices repetidos (reduz ~90 % do tamanho)."""
    geo = json.loads(origem.read_text(encoding="utf-8"))

    def anel(coords):
        out = []
        for x, y in coords:
            p = [round(x, casas), round(y, casas)]
            if not out or out[-1] != p:
                out.append(p)
        if out[0] != out[-1]:
            out.append(out[0])
        return out if len(out) >= 4 else None

    feats = []
    for f in geo["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        novos = []
        for poly in polys:
            aneis = [a for a in (anel(r) for r in poly) if a]
            if aneis:
                novos.append(aneis)
        feats.append({"type": "Feature",
                      "properties": {"uf": f["properties"]["sigla"], "nome": f["properties"]["name"]},
                      "geometry": {"type": "MultiPolygon", "coordinates": novos}})
    destino.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")),
                       encoding="utf-8")


def exportar(mun, pontos, fmun, fuf, fbr, prio, qualidade, fonte: str, proveniencia: dict | None = None,
             extras: dict | None = None) -> dict:
    extras = extras or {}
    for p in (C.PROCESSED, C.POWERBI, C.DASHBOARD_DATA):
        p.mkdir(parents=True, exist_ok=True)

    # ---- dados abertos (CSV, UTF-8 com BOM para abrir direto no Excel) ----
    dim = mun.drop(columns=["chave"])
    dim.to_csv(C.PROCESSED / "municipios.csv", index=False, encoding="utf-8-sig")
    fmun.to_csv(C.PROCESSED / "indicadores_municipio_ano.csv", index=False, encoding="utf-8-sig")
    fuf.to_csv(C.PROCESSED / "indicadores_uf_ano.csv", index=False, encoding="utf-8-sig")
    fbr.to_csv(C.PROCESSED / "indicadores_brasil_ano.csv", index=False, encoding="utf-8-sig")
    prio.to_csv(C.PROCESSED / "prioridade_novos_pontos.csv", index=False, encoding="utf-8-sig")
    # cópia para o dashboard publicar como dados abertos
    abertos = C.DASHBOARD_DATA / "abertos"
    abertos.mkdir(parents=True, exist_ok=True)
    if "planos_mun" in extras:
        (extras["planos_mun"].merge(mun[["cod_ibge", "municipio", "uf"]], on="cod_ibge")
         .to_csv(C.PROCESSED / "planos_municipais_reee.csv", index=False, encoding="utf-8-sig"))
    else:
        (C.PROCESSED / "planos_municipais_reee.csv").unlink(missing_ok=True)
        (abertos / "planos_municipais_reee.csv").unlink(missing_ok=True)
    for nome in ("municipios", "indicadores_municipio_ano", "indicadores_uf_ano",
                 "indicadores_brasil_ano", "prioridade_novos_pontos", "planos_municipais_reee"):
        if (C.PROCESSED / f"{nome}.csv").exists():
            (abertos / f"{nome}.csv").write_bytes((C.PROCESSED / f"{nome}.csv").read_bytes())

    # ---- Power BI: modelo estrela ----
    dim.to_csv(C.POWERBI / "dim_municipio.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"ano": C.ANOS,
                  "meta_municipios": [C.METAS_DECRETO.get(a, {}).get("municipios") for a in C.ANOS],
                  "meta_percentual_peso": [C.METAS_DECRETO.get(a, {}).get("percentual_peso") for a in C.ANOS]}
                 ).to_csv(C.POWERBI / "dim_ano.csv", index=False, encoding="utf-8-sig")
    pontos.to_csv(C.POWERBI / "fato_ponto_ano.csv", index=False, encoding="utf-8-sig")
    fmun.to_csv(C.POWERBI / "fato_municipio_ano.csv", index=False, encoding="utf-8-sig")

    # ---- pacote do dashboard ----
    m = mun.sort_values(["uf", "municipio"]).reset_index(drop=True)
    idx = {c: i for i, c in enumerate(m["cod_ibge"])}
    n, anos = len(m), C.ANOS
    pts = np.full((n, len(anos)), np.nan)
    ton = np.full((n, len(anos)), np.nan)
    for r in fmun[["cod_ibge", "ano", "pontos", "toneladas"]].itertuples(index=False):
        i, j = idx[r.cod_ibge], anos.index(r.ano)
        pts[i, j] = r.pontos
        ton[i, j] = r.toneladas
    vazio = pd.DataFrame(columns=["ano", "entidade", "tipo", "pontos"])
    ent = pontos.groupby(["ano", "entidade"]).size().rename("pontos").reset_index() if len(pontos) else vazio
    if "entidade_ano" in extras:
        ent = extras["entidade_ano"]
    tipo = pontos.groupby(["ano", "tipo"]).size().rename("pontos").reset_index() if len(pontos) else vazio
    ufs = (mun.groupby(["uf", "nome_uf", "regiao"]).size().reset_index()[["uf", "nome_uf", "regiao"]])

    pacote = {
        "meta": {
            "fonte": fonte,
            "proveniencia": proveniencia or {},
            "anos_com_dados": sorted(int(a) for a in fmun.loc[fmun["tem_info"], "ano"].unique())
                              or sorted(int(a) for a in fbr.loc[fbr["pontos"].notna() | fbr["toneladas"].notna(), "ano"]),
            "fontes_relatorios": extras.get("fontes_relatorios", {}),
            "ano_prioridade": int(prio["ano"].iloc[0]) if len(prio) else None,
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "anos": anos,
            "limiar_populacional": C.LIMIAR_POPULACIONAL,
            "hab_por_ponto_decreto": C.HAB_POR_PONTO_DECRETO,
            "metas_decreto": C.METAS_DECRETO,
            "pesos_prioridade": C.PESOS_PRIORIDADE,
        },
        "ufs": _registros(ufs),
        "municipios": {
            "cod": m["cod_ibge"].astype(int).tolist(),
            "nome": m["municipio"].tolist(),
            "uf": m["uf"].tolist(),
            "lat": m["lat"].round(3).tolist(),
            "lon": m["lon"].round(3).tolist(),
            "pop": m["populacao"].astype(int).tolist(),
            "capital": m["capital"].astype(int).tolist(),
            "pontos": [[None if not np.isfinite(v) else int(v) for v in row] for row in pts],
            "ton": [[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in ton],
        },
        "uf_ano": _registros(fuf),
        "brasil_ano": _registros(fbr),
        "entidade_ano": _registros(ent),
        "tipo_ano": _registros(tipo),
        "prioridade": _registros(prio[["cod_ibge", "municipio", "uf", "populacao", "pontos",
                                       "pontos_necessarios", "deficit_pontos", "hab_por_ponto",
                                       "kg_hab", "indice_prioridade", "classe_prioridade"]]
                                  .assign(classe_prioridade=lambda d: d["classe_prioridade"].astype(str))),
        "qualidade": qualidade,
        "uf_entidade": _registros(extras["uf_entidade"]) if "uf_entidade" in extras else [],
        "mun_entidade": _registros(extras["mun_entidade"].astype({"cod_ibge": int})) if "mun_entidade" in extras else [],
        # [cod_ibge, ano, cita_reee, cita_lr, trecho] — trecho só quando cita REEE (mantém o pacote pequeno)
        "planos_mun": [[int(r.cod_ibge), int(r.ano), int(r.cita_reee), int(r.cita_lr), r.trecho if r.cita_reee else ""]
                       for r in extras["planos_mun"].itertuples()] if "planos_mun" in extras else [],
        "planos_uf": _registros(extras["planos_uf"]) if "planos_uf" in extras else [],
    }
    # grava em arquivo temporário e troca de uma vez: o painel nunca lê um JSON pela metade
    tmp = C.DASHBOARD_DATA / "dashboard.json.tmp"
    tmp.write_text(json.dumps(pacote, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(C.DASHBOARD_DATA / "dashboard.json")
    simplificar_geojson(C.RAW_GEO / "brazil-states.geojson", C.DASHBOARD_DATA / "uf.geojson")
    (C.PROCESSED / "qualidade.json").write_text(json.dumps(qualidade, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    return pacote
