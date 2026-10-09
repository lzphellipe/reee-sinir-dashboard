"""Orquestra coleta → tratamento → indicadores → publicação.

Uso:
    python -m reee.pipeline --coletar   # baixa SINIR (MMA) + IBGE e processa  ← dados reais
    python -m reee.pipeline             # processa o que já está em data/raw/
    python -m reee.pipeline --demo      # dados SINTÉTICOS de demonstração

Fontes reconhecidas em data/raw/sinir/ (nesta ordem de preferência):
  1. extraido/<ano>/   – planilhas do módulo Estados e Municípios (coleta automática)
  2. *ponto*, *massa*  – exportações avulsas de pontos de recebimento/massa
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Callable

import pandas as pd

from . import adaptador_sinir, config as C, demo, extract, indicators, planos_sinir, relatorios, transform
from .export import exportar

log = logging.getLogger("reee")


def _populacao_bruta(progresso) -> list[pd.DataFrame]:
    pop = extract.extrair(C.RAW_IBGE)["populacao"]
    if not pop:
        raise FileNotFoundError("População do IBGE ausente: rode com --coletar ou salve data/raw/ibge/populacao.csv")
    progresso(f"População: {', '.join(df['_arquivo'].iloc[0] for df in pop)}")
    return pop


def executar(usar_demo: bool = False, seed: int = 42, coletar: bool = False, forcar: bool = False,
             progresso: Callable[[str], None] = log.info) -> dict:
    q: dict = {}
    proveniencia: dict = {}
    declaracoes = None
    rel = None

    if usar_demo:
        progresso(f"Gerando dados sintéticos de demonstração (seed={seed})")
        demo.gerar(seed)
        brutos = extract.extrair(C.RAW_DEMO)
        fonte = "demo"
        mun = transform.dim_municipio(brutos["populacao"])
        pontos = transform.limpar_pontos(brutos["pontos"], mun, q)
        massa_mun, massa_uf = transform.limpar_massa(brutos["massa"], mun, q)
    else:
        if coletar:
            from . import coleta
            progresso("Coletando dados oficiais (MMA/SINIR e IBGE)")
            man = coleta.sincronizar(forcar, progresso)["manifesto"]
            if man.get("falhas"):
                q["coleta_falhas"] = man["falhas"]
        mun = transform.dim_municipio(_populacao_bruta(progresso))
        extraido = C.RAW_SINIR / "extraido"
        if extraido.exists() and any(extraido.iterdir()):
            fonte = "sinir_estados_municipios"
            progresso("Lendo planilhas do módulo Estados e Municípios do SINIR")
            declaracoes, inv = adaptador_sinir.processar(set(mun["cod_ibge"]))
            md = adaptador_sinir.salvar_inventario(inv)
            progresso(f"Inventário das planilhas: {md.name} (em data/processed)")
            q["abas_lidas"] = sum(1 for r in inv if "erro" not in r)
            q["abas_com_codigo_ibge"] = sum(1 for r in inv if r.get("coluna_ibge"))
            for campo in ("pontos", "toneladas", "possui"):
                anos = sorted({r["ano"] for r in inv if campo in (r.get("escolhas") or {})})
                q[f"anos_com_campo_{campo}"] = ", ".join(map(str, anos)) or "nenhum"
            q["declaracoes_municipio_ano"] = int(len(declaracoes))
            if declaracoes[["pontos", "possui"]].notna().sum().sum() == 0:
                q["aviso"] = ("Nenhuma coluna de pontos de eletroeletrônicos foi reconhecida. "
                              "Veja data/processed/inventario_sinir.md e ajuste data/raw/sinir/mapeamento.json.")
                progresso("ATENÇÃO: " + q["aviso"])
                if relatorios.disponivel():
                    # sem dado municipal útil: mantém os indicadores por UF dos relatórios
                    fonte = "relatorios_entidades"
                    q["aviso"] += " Enquanto isso, o painel usa os relatórios das entidades gestoras."
                    progresso("Usando os relatórios das entidades gestoras (dados por estado)")
            pontos = pd.DataFrame(columns=["ano", "cod_ibge", "entidade", "tipo"])
            massa_mun = pd.DataFrame(columns=["ano", "cod_ibge", "toneladas"])
            massa_uf = pd.DataFrame(columns=["ano", "uf", "toneladas"])
            man_path = C.RAW_SINIR / "manifesto.json"
            if man_path.exists():
                man = json.loads(man_path.read_text(encoding="utf-8"))
                proveniencia = {a: {k: v.get(k) for k in ("nome", "url", "modificado", "coletado_em", "sha256")}
                                for a, v in man.get("arquivos", {}).items()}
        elif extract.extrair(C.RAW_SINIR)["pontos"]:
            fonte = "sinir_arquivos"
            brutos = extract.extrair(C.RAW_SINIR)
            pontos = transform.limpar_pontos(brutos["pontos"], mun, q)
            massa_mun, massa_uf = transform.limpar_massa(brutos["massa"], mun, q)
        elif relatorios.disponivel():
            # Só há os relatórios das entidades gestoras: dados por UF, não por município
            fonte = "relatorios_entidades"
            progresso("Lendo relatórios anuais das entidades gestoras (SINIR)")
            declaracoes = pd.DataFrame(columns=["cod_ibge", "ano", "pontos", "toneladas", "possui"])
            pontos = pd.DataFrame(columns=["ano", "cod_ibge", "entidade", "tipo"])
            massa_mun = pd.DataFrame(columns=["ano", "cod_ibge", "toneladas"])
            massa_uf = pd.DataFrame(columns=["ano", "uf", "toneladas"])
        else:
            raise FileNotFoundError("Nenhum dado do SINIR em data/raw/sinir/. Rode com --coletar.")
        if relatorios.disponivel():
            rel = relatorios.carregar(mun, q)
            progresso(f"Relatórios das entidades: {len(rel['uf_entidade'])} linhas por UF, "
                      f"{len(rel['mun_entidade'])} municípios com pontos listados")
    planos = None
    if not usar_demo and (C.RAW_SINIR / "extraido").exists():
        progresso("Classificando os planos municipais de resíduos (menções a eletroeletrônicos)")
        planos = planos_sinir.processar(mun, q)
        if len(planos):
            progresso(f"Planos municipais: {len(planos)} declarações; {int(planos['cita_reee'].sum())} citam eletroeletrônicos")
    q = {"fonte": fonte, **q}

    pontos_mun = (pontos.groupby(["cod_ibge", "ano"]).size().rename("pontos").reset_index()
                  if len(pontos) else pd.DataFrame(columns=["cod_ibge", "ano", "pontos"]))
    progresso("Calculando indicadores")
    fmun = indicators.fato_municipio_ano(mun, pontos_mun, massa_mun, declaracoes)
    fuf = indicators.fato_uf_ano(fmun, massa_uf)
    fbr = indicators.fato_brasil_ano(fuf)
    prio = indicators.prioridade(fmun, mun)
    extras: dict = {}
    if rel is not None:
        if fonte == "relatorios_entidades":
            fuf, fbr = relatorios.aplicar(fuf, fbr, fmun, rel)
            prio = prio.iloc[0:0]
        extras = {
            "entidade_ano": rel["nacional"][["ano", "entidade", "pontos", "municipios_atendidos", "toneladas"]],
            "uf_entidade": rel["uf_entidade"],
            "mun_entidade": rel["mun_entidade"],
            "fontes_relatorios": rel["fontes"],
        }

    if planos is not None and len(planos):
        extras["planos_mun"] = planos
        puf = planos_sinir.agregar_uf(planos, mun)
        extras["planos_uf"] = puf
        fuf = fuf.merge(puf, on=["uf", "ano"], how="left")
        pbr = puf.groupby("ano")[["planos_declarados", "planos_citam_reee"]].sum().reset_index()
        pbr["pct_planos_reee"] = (pbr["planos_citam_reee"] / pbr["planos_declarados"] * 100).round(1)
        fbr = fbr.merge(pbr, on="ano", how="left")

    progresso("Publicando arquivos do painel")
    pacote = exportar(mun, pontos, fmun, fuf, fbr, prio, q, fonte, proveniencia, extras)
    ult = fbr.iloc[-1]
    com_pontos = fbr.dropna(subset=["pontos"])
    if len(com_pontos):
        u = com_pontos.iloc[-1]
        progresso(f"Concluído: {int(u.ano)} com {u.pontos:.0f} pontos de recebimento informados")
    else:
        progresso("Concluído (nenhum ano com número de pontos)")
    return pacote


def main() -> None:
    ap = argparse.ArgumentParser(description="SINIR → indicadores de logística reversa de REEE")
    ap.add_argument("--coletar", action="store_true", help="baixar/atualizar dados oficiais antes de processar")
    ap.add_argument("--forcar", action="store_true", help="com --coletar, ignora o cache de downloads")
    ap.add_argument("--demo", action="store_true", help="usar dados sintéticos de demonstração")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    executar(args.demo, args.seed, args.coletar, args.forcar)


if __name__ == "__main__":
    main()
