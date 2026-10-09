"""Adaptador das planilhas do módulo Estados e Municípios do SINIR.

As planilhas são declarações dos próprios municípios e seu layout muda a cada
ano. Em vez de nomes fixos de coluna, o adaptador:

1. acha a linha de cabeçalho (inclusive cabeçalhos agrupados em 2 linhas,
   como "Eletroeletrônicos" sobre "Possui PEV?" | "Quantidade");
2. acha a coluna de código IBGE pelo nome OU pelos valores (7 dígitos);
3. pontua cada coluna para três campos de REEE:
   - pontos     : nº de pontos/PEVs/locais de entrega de eletroeletrônicos
   - toneladas  : massa coletada/recebida de eletroeletrônicos (t ou kg)
   - possui     : se o município tem sistema/ponto de LR de eletroeletrônicos (Sim/Não)
4. aceita também o formato "longo" (colunas Pergunta | Resposta);
5. grava um inventário (data/processed/inventario_sinir.md/.json) com todas
   as abas, colunas e escolhas, para auditoria e ajuste fino.

Se a detecção automática errar, crie data/raw/sinir/mapeamento.json:
    {"*":    {"pontos": "nome da coluna", "toneladas": "...", "possui": "...", "cod_ibge": "..."},
     "2023": {"pontos": "outro nome para 2023"}}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .utils import normalizar_texto, numero_br

RE_REEE = re.compile(r"eletroeletr|eletro eletr|\breee\b|eletronic|e lixo|lixo eletron|eletrodomest")
RE_PONTO = re.compile(r"ponto|pev|posto|local|entrega voluntaria|ecoponto|coleta")
RE_QTD = re.compile(r"\bquant|\bqtd|\bqtde|\bnumero|\bn o\b|\bno de\b|\btotal\b|\bnum\b")
RE_MASSA = re.compile(r"tonelad|\bton\b|\bt\b|massa|peso|\bkg\b|quilo")
RE_POSSUI = re.compile(r"possui|existe|\bha\b|dispoe|implant|tem |conta com|sistema de logistica reversa")
RE_IBGE = re.compile(r"ibge|cod.*munic|codigo do municipio|geocod|cod mun|cd mun|id municipio")
RE_PERGUNTA = re.compile(r"pergunta|questao|quesito|indicador|item|descricao")
RE_RESPOSTA = re.compile(r"resposta|valor|conteudo|informacao")
SIM = {"sim", "s", "yes", "1", "true", "possui", "existe"}
NAO = {"nao", "n", "no", "0", "false", "nao possui", "inexistente"}


# --------------------------------------------------------------------------- leitura
def _ler_abas(arquivo: Path) -> dict[str, pd.DataFrame]:
    suf = arquivo.suffix.lower()
    if suf == ".csv":
        from .extract import ler_tabela
        df = ler_tabela(arquivo).drop(columns=["_arquivo", "_ano_arquivo"])
        return {"csv": pd.concat([pd.DataFrame([df.columns], columns=df.columns), df], ignore_index=True)}
    engine = {".ods": "odf", ".xls": None}.get(suf)
    return pd.read_excel(arquivo, sheet_name=None, header=None, dtype=str, engine=engine)


def _linha_cabecalho(bruto: pd.DataFrame, max_linhas: int = 25) -> int:
    melhor, pont = 0, -1.0
    for i in range(min(max_linhas, len(bruto))):
        vals = [normalizar_texto(v) for v in bruto.iloc[i].tolist()]
        textos = [v for v in vals if v and not re.fullmatch(r"[\d ]+", v)]
        if not textos:
            continue
        p = len(textos) + 5 * any(re.search(r"munic|ibge|\buf\b", v) for v in textos)
        if p > pont:
            melhor, pont = i, p
    return melhor


def _montar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    h = _linha_cabecalho(bruto)
    cab = [str(v).strip() if pd.notna(v) else "" for v in bruto.iloc[h].tolist()]
    if h > 0:  # cabeçalho agrupado: propaga o grupo da linha de cima
        grupo = pd.Series([str(v).strip() if pd.notna(v) else None for v in bruto.iloc[h - 1].tolist()]).ffill()
        if grupo.notna().sum() >= 2:
            cab = [f"{g} | {c}" if g and c and normalizar_texto(g) != normalizar_texto(c) else (c or g or "")
                   for g, c in zip(grupo.fillna(""), cab)]
    vistos: dict[str, int] = {}
    nomes = []
    for i, c in enumerate(cab):
        c = c or f"coluna_{i}"
        vistos[c] = vistos.get(c, 0) + 1
        nomes.append(c if vistos[c] == 1 else f"{c} ({vistos[c]})")
    df = bruto.iloc[h + 1:].copy()
    df.columns = nomes
    df = df.dropna(how="all")
    return df, h


# --------------------------------------------------------------------------- detecção
_RE_SEPARADORES = re.compile(r"[\s.\-/]")


def para_codigo(valor):
    """Converte uma célula em código IBGE (6 ou 7 dígitos) ou NA.

    Não junta dígitos de textos longos: uma célula como "Tel. (35) 3551-0000,
    CNPJ 12.345.678/0001-90" não pode virar um número gigante.
    """
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return pd.NA
    t = str(valor).strip()
    t = re.sub(r"\.0+$", "", t)          # 3550308.0 vindo do Excel
    t = _RE_SEPARADORES.sub("", t)        # 355030-8, 3.550.308
    return int(t) if re.fullmatch(r"\d{6,7}", t) else pd.NA


def _codigos(serie: pd.Series) -> pd.Series:
    return pd.array([para_codigo(v) for v in serie], dtype="Int64")


def _col_ibge(df: pd.DataFrame, validos: set[int], forcado: str | None) -> str | None:
    if forcado:
        return _achar(df, forcado)
    melhores = []
    for c in df.columns:
        s = df[c].dropna()
        if s.empty:
            continue
        n = pd.Series(_codigos(s)).dropna().astype("int64")
        n = n.reindex(range(len(s)))  # taxa calculada sobre as células preenchidas
        taxa7 = n.isin(validos).mean() if len(n) else 0
        taxa6 = (n.isin({v // 10 for v in validos})).mean() if len(n) else 0
        nome = RE_IBGE.search(normalizar_texto(c)) is not None
        melhores.append((max(taxa7, taxa6) + 0.3 * nome, c))
    melhores.sort(reverse=True)
    return melhores[0][1] if melhores and melhores[0][0] >= 0.6 else None


def _achar(df: pd.DataFrame, nome: str) -> str | None:
    alvo = normalizar_texto(nome)
    for c in df.columns:
        if normalizar_texto(c) == alvo:
            return c
    for c in df.columns:
        if alvo in normalizar_texto(c):
            return c
    return None


def _perfil(serie: pd.Series) -> dict:
    s = serie.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return {"preenchido": 0.0, "sim_nao": 0.0, "numerico": 0.0, "inteiro": 0.0}
    norm = s.map(normalizar_texto)
    nums = s.map(numero_br)
    num_ok = nums.notna()
    return {
        "preenchido": len(s) / len(serie),
        "sim_nao": norm.isin(SIM | NAO).mean(),
        "numerico": num_ok.mean(),
        "inteiro": (nums[num_ok] % 1 == 0).mean() if num_ok.any() else 0.0,
    }


def pontuar(nome: str, serie: pd.Series) -> dict[str, float]:
    """Pontuação 0–1 da coluna para cada campo canônico."""
    n = normalizar_texto(nome)
    if not RE_REEE.search(n):
        return {"pontos": 0.0, "toneladas": 0.0, "possui": 0.0}
    p = _perfil(serie)
    massa = bool(RE_MASSA.search(n))
    ponto = bool(RE_PONTO.search(n))
    qtd = bool(RE_QTD.search(n))
    return {
        "pontos": (0.4 * ponto + 0.25 * qtd + 0.25 * p["numerico"] * p["inteiro"] + 0.1 * p["preenchido"])
                  * (0.3 if massa else 1.0) * (0.3 if p["sim_nao"] > 0.5 else 1.0),
        "toneladas": (0.5 * massa + 0.3 * p["numerico"] + 0.2 * p["preenchido"]) * (1.0 if massa else 0.4)
                     * (0.3 if p["sim_nao"] > 0.5 else 1.0),
        "possui": (0.4 * bool(RE_POSSUI.search(n)) + 0.5 * p["sim_nao"] + 0.1 * p["preenchido"])
                  * (0.2 if p["numerico"] > 0.8 else 1.0),
    }


def _sim_nao(v) -> float:
    t = normalizar_texto(v)
    if t in SIM or t.startswith("sim"):
        return 1.0
    if t in NAO or t.startswith("nao"):
        return 0.0
    return np.nan


def _formato_longo(df: pd.DataFrame, col_ibge: str):
    perg = next((c for c in df.columns if RE_PERGUNTA.search(normalizar_texto(c))), None)
    resp = next((c for c in df.columns if RE_RESPOSTA.search(normalizar_texto(c))), None)
    if not perg or not resp:
        return None
    sub = df[df[perg].fillna("").map(lambda t: bool(RE_REEE.search(normalizar_texto(t))))]
    if sub.empty:
        return None
    largo = sub.pivot_table(index=col_ibge, columns=perg, values=resp, aggfunc="first").reset_index()
    largo.columns = [str(c) for c in largo.columns]
    return largo


# --------------------------------------------------------------------------- principal
def _mapeamento() -> dict:
    p = C.RAW_SINIR / "mapeamento.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def processar_ano(ano: int, planilhas: list[Path], validos: set[int], limiar: float = 0.45):
    mapa = {**_mapeamento().get("*", {}), **_mapeamento().get(str(ano), {})}
    inventario, partes = [], []
    for arq in planilhas:
        try:
            abas = _ler_abas(arq)
        except Exception as e:  # noqa: BLE001
            inventario.append({"ano": ano, "arquivo": arq.name, "erro": str(e)})
            continue
        for aba, bruto in abas.items():
            if bruto.shape[0] < 2 or bruto.shape[1] < 2:
                continue
            try:
                parte = _processar_aba(ano, arq, aba, bruto, validos, mapa, limiar, inventario)
            except Exception as e:  # noqa: BLE001 – uma aba com problema não derruba as demais
                inventario.append({"ano": ano, "arquivo": arq.name, "aba": aba,
                                   "erro": f"{e.__class__.__name__}: {e}"})
                continue
            if parte is not None:
                partes.append(parte)
    if not partes:
        return pd.DataFrame(columns=["cod_ibge", "ano", "pontos", "toneladas", "possui"]), inventario
    return _consolidar(partes), inventario


def _processar_aba(ano, arq, aba, bruto, validos, mapa, limiar, inventario):
    df, h = _montar(bruto)
    reg = {"ano": ano, "arquivo": arq.name, "aba": aba, "linhas": int(len(df)),
           "linha_cabecalho": h + 1, "colunas": list(map(str, df.columns))[:400]}
    ibge = _col_ibge(df, validos, mapa.get("cod_ibge"))
    reg["coluna_ibge"] = ibge
    if not ibge:
        reg["observacao"] = "sem coluna de código IBGE (provavelmente dado estadual ou agregado)"
        inventario.append(reg)
        return None
    longo = _formato_longo(df, ibge)
    if longo is not None:
        df, reg["formato"] = longo, "longo (pergunta/resposta)"
    escolhas, candidatos = {}, []
    for campo in ("pontos", "toneladas", "possui"):
        if mapa.get(campo):
            col = _achar(df, mapa[campo])
            if col:
                escolhas[campo] = {"coluna": col, "pontuacao": 1.0, "origem": "mapeamento.json"}
            continue
        notas = sorted(((pontuar(c, df[c])[campo], c) for c in df.columns if c != ibge), reverse=True)
        candidatos += [{"campo": campo, "coluna": c, "pontuacao": round(s, 3)} for s, c in notas[:3] if s > 0]
        if notas and notas[0][0] >= limiar:
            escolhas[campo] = {"coluna": notas[0][1], "pontuacao": round(notas[0][0], 3), "origem": "automática"}
    reg["escolhas"], reg["candidatos"] = escolhas, candidatos
    inventario.append(reg)

    cod = pd.Series(_codigos(df[ibge]), index=df.index)
    seis = (cod < 1_000_000).fillna(False)
    if seis.any():
        mapa6 = {v // 10: v for v in validos}
        cod[seis] = cod[seis].map(mapa6).astype("Int64")
    out = pd.DataFrame({"cod_ibge": cod, "ano": ano})
    out["pontos"] = df[escolhas["pontos"]["coluna"]].map(numero_br).values if "pontos" in escolhas else np.nan
    if "toneladas" in escolhas:
        col = escolhas["toneladas"]["coluna"]
        fator = 0.001 if re.search(r"\bkg\b|quilo", normalizar_texto(col)) else 1.0
        out["toneladas"] = df[col].map(numero_br).values * fator
    else:
        out["toneladas"] = np.nan
    out["possui"] = df[escolhas["possui"]["coluna"]].map(_sim_nao).values if "possui" in escolhas else np.nan
    out = out[out["cod_ibge"].isin(validos).fillna(False)]
    if len(out):
        out["_aba"] = f"{arq.name}:{aba}"
        return out
    return None


def _consolidar(partes):
    tudo = pd.concat(partes, ignore_index=True)
    # Um município pode aparecer em várias abas: prioriza a linha com mais campos de REEE
    tudo["_info"] = tudo[["pontos", "toneladas", "possui"]].notna().sum(axis=1)
    tudo = (tudo.sort_values("_info", ascending=False)
            .groupby(["cod_ibge", "ano"], as_index=False)
            .agg({"pontos": "first", "toneladas": "first", "possui": "first"}))
    tudo["cod_ibge"] = tudo["cod_ibge"].astype(int)
    return tudo


def processar(validos: set[int], pasta: Path | None = None):
    """Lê data/raw/sinir/extraido/<ano>/ e devolve (declaracoes, inventario)."""
    pasta = pasta or (C.RAW_SINIR / "extraido")
    decl, inv = [], []
    for dir_ano in sorted(p for p in pasta.iterdir() if p.is_dir() and p.name.isdigit()):
        ano = int(dir_ano.name)
        if not C.ANO_INICIAL <= ano <= C.ANO_FINAL:
            continue
        planilhas = sorted(p for p in dir_ano.rglob("*") if p.suffix.lower() in {".xlsx", ".xls", ".csv", ".ods"})
        d, i = processar_ano(ano, planilhas, validos)
        decl.append(d)
        inv += i
    declaracoes = pd.concat(decl, ignore_index=True) if decl else pd.DataFrame(
        columns=["cod_ibge", "ano", "pontos", "toneladas", "possui"])
    return declaracoes, inv


def salvar_inventario(inv: list[dict], destino_dir: Path | None = None) -> Path:
    destino_dir = destino_dir or C.PROCESSED
    destino_dir.mkdir(parents=True, exist_ok=True)
    (destino_dir / "inventario_sinir.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = ["# Inventário das planilhas do SINIR", "",
              "Gerado automaticamente. Confira se as colunas escolhidas são as corretas; se não forem, "
              "indique-as em `data/raw/sinir/mapeamento.json`.", ""]
    for r in inv:
        linhas.append(f"## {r['ano']} · {r['arquivo']} · aba `{r.get('aba', '-')}`")
        if "erro" in r:
            linhas += [f"- **Erro de leitura:** {r['erro']}", ""]
            continue
        linhas.append(f"- {r['linhas']} linhas, cabeçalho na linha {r['linha_cabecalho']}; coluna IBGE: `{r.get('coluna_ibge')}`")
        if r.get("formato"):
            linhas.append(f"- Formato: {r['formato']}")
        if r.get("observacao"):
            linhas.append(f"- {r['observacao']}")
        for campo, e in (r.get("escolhas") or {}).items():
            linhas.append(f"- **{campo}** ← `{e['coluna']}` (pontuação {e['pontuacao']}, {e['origem']})")
        cand = [c for c in r.get("candidatos", []) if c["coluna"] not in
                {e["coluna"] for e in (r.get("escolhas") or {}).values()}]
        if cand:
            linhas.append("- Outras candidatas: " + "; ".join(f"{c['campo']}: `{c['coluna']}` ({c['pontuacao']})" for c in cand[:6]))
        reee = [c for c in r["colunas"] if RE_REEE.search(normalizar_texto(c))]
        if reee:
            linhas.append("- Colunas que citam eletroeletrônicos: " + "; ".join(f"`{c}`" for c in reee[:15]))
        linhas.append("")
    md = destino_dir / "inventario_sinir.md"
    md.write_text("\n".join(linhas), encoding="utf-8")
    return md
