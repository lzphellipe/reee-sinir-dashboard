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


def exportar(mun, pontos, fmun, fuf, fbr, prio, qualidade, fonte: str) -> dict:
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
    for nome in ("municipios", "indicadores_municipio_ano", "indicadores_uf_ano",
                 "indicadores_brasil_ano", "prioridade_novos_pontos"):
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
    pts = np.zeros((n, len(anos)), dtype=int)
    ton = np.full((n, len(anos)), np.nan)
    for r in fmun[["cod_ibge", "ano", "pontos", "toneladas"]].itertuples(index=False):
        i, j = idx[r.cod_ibge], anos.index(r.ano)
        pts[i, j] = r.pontos
        ton[i, j] = r.toneladas
    ent = (pontos.groupby(["ano", "entidade"]).size().rename("pontos").reset_index())
    tipo = (pontos.groupby(["ano", "tipo"]).size().rename("pontos").reset_index())
    ufs = (mun.groupby(["uf", "nome_uf", "regiao"]).size().reset_index()[["uf", "nome_uf", "regiao"]])

    pacote = {
        "meta": {
            "fonte": fonte,
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
            "pontos": pts.tolist(),
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
    }
    (C.DASHBOARD_DATA / "dashboard.json").write_text(
        json.dumps(pacote, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    simplificar_geojson(C.RAW_GEO / "brazil-states.geojson", C.DASHBOARD_DATA / "uf.geojson")
    (C.PROCESSED / "qualidade.json").write_text(json.dumps(qualidade, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    return pacote
