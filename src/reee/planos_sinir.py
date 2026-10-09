"""Planos municipais de resíduos declarados ao SINIR: o município prevê ação para REEE?

O módulo Estados e Municípios do SINIR não traz números de eletroeletrônicos,
mas os municípios descrevem, em texto livre, as metas, programas e soluções
compartilhadas dos seus planos de gestão de resíduos. Este módulo:

1. lê as planilhas municipais (Diagnóstico, Soluções Compartilhadas,
   Mecanismo para Criação de Fonte) de cada ano;
2. casa "Município Declarante" + "UF Declarante" com o cadastro IBGE
   (as planilhas não trazem o código IBGE);
3. classifica cada declaração: cita eletroeletrônicos? cita logística reversa?
4. guarda o trecho exato que motivou a classificação, como evidência.

Limite metodológico: é classificação por palavras-chave. Citar não prova que
a ação foi executada; não citar não prova que ela não exista.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import pandas as pd

from . import config as C
from .extract import ler_tabela
from .utils import chave_municipio, normalizar_texto

# --- vocabulário (aplicado ao texto normalizado: minúsculo, sem acento) ------
def _re(padrao: str) -> re.Pattern:
    return re.compile(padrao.replace(" ", r"\s+"))


RE_REEE = _re(
    r"eletroeletronic\w*|eletro eletronic\w*|eletrodomestic\w*|\breee\b|\be lixo\b|"
    r"lixo eletronic\w*|lixo tecnologic\w*|sucata eletronic\w*|"
    r"residuos? (?:solidos )?(?:de )?(?:equipamentos )?eletr(?:ic|on)\w*|"
    r"equipamentos? eletr(?:ic|on)\w*|"
    r"\beletronicos\b"
)
# "eletrônicos" como adjetivo de documento/sistema não é resíduo
RE_FALSO = _re(
    r"(?:nota|notas) fisca\w* eletronic\w*|\b(?:sistema|sistemas|meio|meios|processo|processos|documento|documentos|"
    r"formulario|formularios|manifesto|mtr|cadastro|plataforma|controle|correio|endereco|governo|edital|"
    r"protocolo|assinatura|certificado|diario|portal|pregao|ponto|balanca|balancas) eletronic\w*"
)
RE_LR = _re(r"logistica reversa")


def _alinhado(texto: str) -> str:
    """Versão minúscula e sem acento com o MESMO comprimento do original (posições batem)."""
    import unicodedata
    saida = []
    for ch in texto:
        base = unicodedata.normalize("NFKD", ch)[:1].lower()
        saida.append(base if base.isascii() and base.isalnum() else " ")
    return "".join(saida)


# colunas de texto que descrevem ações (comparação feita no nome normalizado)
COLUNAS_TEXTO = ("meta programa", "meta programa descritivo", "solucao", "solucao consorcio",
                 "descricao mecanismo fonte", "caracterizacao descricao")
ARQUIVOS = re.compile(r"municipal", re.I)

NOMES_UF = None


def _uf_sigla(valor) -> str:
    """Aceita "MG", "Minas Gerais" ou "MINAS GERAIS"."""
    global NOMES_UF
    if NOMES_UF is None:
        est = pd.read_csv(C.RAW_IBGE / "estados_kelvins.csv", encoding="utf-8-sig")
        NOMES_UF = {normalizar_texto(n): u for n, u in zip(est["nome"], est["uf"])}
        NOMES_UF.update({normalizar_texto(u): u for u in est["uf"]})
    return NOMES_UF.get(normalizar_texto(valor), str(valor).strip().upper()[:2])


def _limpa_nome(nome) -> str:
    t = str(nome or "").strip()
    t = re.sub(r"\s*[-/(]\s*[A-Za-z]{2}\)?\s*$", "", t)  # "Guaranésia - MG", "Guaranésia (MG)"
    return t


def classificar(texto) -> tuple[bool, bool, str]:
    """(cita_reee, cita_lr, trecho). O trecho sai do texto original, com palavras inteiras."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return False, False, ""
    original = re.sub(r"\s+", " ", str(texto)).strip()
    norm = _alinhado(original)
    limpo = RE_FALSO.sub(lambda m: " " * len(m.group()), norm)  # apaga falsos positivos sem mudar posições
    lr = bool(RE_LR.search(norm))
    m = RE_REEE.search(limpo)
    if not m:
        return False, lr, ""
    ini, fim = max(0, m.start() - 70), min(len(original), m.end() + 90)
    while ini > 0 and original[ini - 1] != " ":
        ini -= 1
    while fim < len(original) and original[fim] != " ":
        fim += 1
    trecho = ("…" if ini > 0 else "") + original[ini:fim].strip() + ("…" if fim < len(original) else "")
    return True, lr, trecho


def _coluna(df: pd.DataFrame, *alvos: str) -> str | None:
    for c in df.columns:
        n = normalizar_texto(c)
        if any(n == a or n.startswith(a + " ") or n.rstrip(" 0123456789") == a for a in alvos):
            return c
    return None


def _casar(df: pd.DataFrame, mun: pd.DataFrame, q: dict) -> pd.Series:
    chave = dict(zip(mun["chave"], mun["cod_ibge"]))
    por_uf = {uf: (list(g["cod_ibge"]), [normalizar_texto(n) for n in g["municipio"]], list(g["municipio"]))
              for uf, g in mun.groupby("uf")}
    cache: dict[tuple, object] = {}
    cods = []
    for nome, uf in zip(df["_mun"], df["_uf"]):
        k = (nome, uf)
        if k not in cache:
            cod = chave.get(chave_municipio(nome, uf))
            if cod is None and uf in por_uf:
                codigos, nomes, oficiais = por_uf[uf]
                alvo = normalizar_texto(nome)
                prox = difflib.get_close_matches(alvo, nomes, n=1, cutoff=0.88)
                if prox:
                    i = nomes.index(prox[0])
                    cod = codigos[i]
                    q.setdefault("planos_nomes_corrigidos", []).append(f"{nome}/{uf} → {oficiais[i]}")
            cache[k] = cod
            if cod is None:
                q.setdefault("planos_nao_casados", []).append(f"{nome}/{uf}")
        cods.append(cache[k])
    return pd.Series(pd.array(cods, dtype="Int64"), index=df.index)


def processar(mun: pd.DataFrame, q: dict, pasta: Path | None = None) -> pd.DataFrame:
    """Uma linha por município e ano: declarou, cita_reee, cita_lr, trecho, fonte."""
    pasta = pasta or (C.RAW_SINIR / "extraido")
    colunas = ["cod_ibge", "ano", "declarou_plano", "cita_reee", "cita_lr", "trecho", "fonte"]
    if not pasta.exists():
        return pd.DataFrame(columns=colunas)
    partes = []
    for dir_ano in sorted(p for p in pasta.iterdir() if p.is_dir() and p.name.isdigit()):
        ano = int(dir_ano.name)
        for arq in sorted(dir_ano.rglob("*")):
            if arq.suffix.lower() not in {".csv", ".xlsx", ".xls"} or not ARQUIVOS.search(arq.name):
                continue
            try:
                df = ler_tabela(arq)
            except Exception as e:  # noqa: BLE001
                q.setdefault("planos_arquivos_com_erro", []).append(f"{arq.name}: {e}")
                continue
            c_mun = _coluna(df, "municipio declarante", "municipio")
            c_uf = _coluna(df, "uf declarante", "uf")
            if not c_mun or not c_uf:
                continue
            textos = [c for c in df.columns if any(normalizar_texto(c).rstrip(" 0123456789") == t for t in COLUNAS_TEXTO)]
            df = df.assign(_mun=df[c_mun].map(_limpa_nome), _uf=df[c_uf].map(_uf_sigla))
            df = df[df["_mun"].map(normalizar_texto) != normalizar_texto(c_mun)]  # cabeçalho repetido
            df = df[df["_mun"].str.len() > 0]
            if df.empty:
                continue
            df["cod_ibge"] = _casar(df, mun, q)
            df = df.dropna(subset=["cod_ibge"])
            res = []
            for _, linha in df.iterrows():
                achou = (False, False, "", "")
                lr_algum = False
                for c in textos:
                    reee, lr, trecho = classificar(linha[c])
                    lr_algum |= lr
                    if reee and not achou[0]:
                        achou = (True, lr, trecho, f"{arq.name} · {c}")
                res.append((int(linha["cod_ibge"]), ano, True, achou[0], lr_algum, achou[2], achou[3]))
            partes.append(pd.DataFrame(res, columns=colunas))
    if not partes:
        return pd.DataFrame(columns=colunas)
    tudo = pd.concat(partes, ignore_index=True)
    # várias linhas por município (uma por meta/solução): consolida, preferindo a que cita REEE
    tudo = tudo.sort_values(["cita_reee", "cita_lr"], ascending=False)
    agg = (tudo.groupby(["cod_ibge", "ano"], as_index=False)
           .agg(declarou_plano=("declarou_plano", "max"), cita_reee=("cita_reee", "max"),
                cita_lr=("cita_lr", "max"), trecho=("trecho", "first"), fonte=("fonte", "first")))
    q["planos_declaracoes"] = int(len(agg))
    q["planos_citam_reee"] = int(agg["cita_reee"].sum())
    for chave_q in ("planos_nomes_corrigidos", "planos_nao_casados"):
        if chave_q in q:
            q[chave_q] = sorted(set(q[chave_q]))[:50]
    return agg.sort_values(["ano", "cod_ibge"]).reset_index(drop=True)


def agregar_uf(planos: pd.DataFrame, mun: pd.DataFrame) -> pd.DataFrame:
    if planos.empty:
        return pd.DataFrame(columns=["uf", "ano", "planos_declarados", "planos_citam_reee", "pct_planos_reee"])
    p = planos.merge(mun[["cod_ibge", "uf"]], on="cod_ibge")
    a = (p.groupby(["uf", "ano"]).agg(planos_declarados=("declarou_plano", "sum"),
                                      planos_citam_reee=("cita_reee", "sum")).reset_index())
    a["pct_planos_reee"] = (a["planos_citam_reee"] / a["planos_declarados"] * 100).round(1)
    return a
