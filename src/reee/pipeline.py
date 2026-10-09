"""Orquestra o ETL completo.

Uso:
    python -m reee.pipeline --demo      # gera e usa dados SINTÉTICOS
    python -m reee.pipeline             # usa data/raw/sinir + data/raw/ibge
"""
from __future__ import annotations

import argparse
import logging

from . import config as C
from . import demo, extract, indicators, transform
from .export import exportar

log = logging.getLogger("reee")


def executar(usar_demo: bool = False, seed: int = 42) -> dict:
    if usar_demo:
        log.info("Gerando dados sintéticos de demonstração (seed=%s)", seed)
        demo.gerar(seed)
        brutos = extract.extrair(C.RAW_DEMO)
        fonte = "demo"
    else:
        brutos = extract.extrair(C.RAW_SINIR)
        brutos["populacao"] = extract.extrair(C.RAW_IBGE)["populacao"] or brutos["populacao"]
        fonte = "sinir"
    log.info("Arquivos lidos: %s", {k: len(v) for k, v in brutos.items()})

    q: dict = {"fonte": fonte}
    mun = transform.dim_municipio(brutos["populacao"])
    pontos = transform.limpar_pontos(brutos["pontos"], mun, q)
    massa_mun, massa_uf = transform.limpar_massa(brutos["massa"], mun, q)

    fmun = indicators.fato_municipio_ano(mun, pontos, massa_mun)
    fuf = indicators.fato_uf_ano(fmun, massa_uf)
    fbr = indicators.fato_brasil_ano(fuf)
    prio = indicators.prioridade(fmun, mun)

    pacote = exportar(mun, pontos, fmun, fuf, fbr, prio, q, fonte)
    log.info("Qualidade: %s", q)
    ult = fbr.iloc[-1]
    log.info("%s: %d pontos, %.0f t, %.1f %% da população em município com ponto",
             int(ult.ano), ult.pontos, ult.toneladas or 0, ult.pct_pop_coberta)
    return pacote


def main() -> None:
    ap = argparse.ArgumentParser(description="ETL SINIR → indicadores de logística reversa de REEE")
    ap.add_argument("--demo", action="store_true", help="usar dados sintéticos de demonstração")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    executar(args.demo, args.seed)


if __name__ == "__main__":
    main()
