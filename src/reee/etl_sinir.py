"""ETL do SINIR – módulo Estados e Municípios (exercícios 2019–2025).

Adaptado do script `etl_sinir.py` criado pela equipe (Luiz Felipe Alves Lopes).
Mantém a lógica original:

* lê os ZIPs oficiais publicados pelo MMA/SINIR (links diretos do portal);
* gera o inventário de todos os arquivos e abas (`inventario_arquivos_sinir.csv`);
* procura, em TODAS as colunas e arquivos, linhas com termos ligados a
  eletroeletrônicos ou logística reversa e as guarda com rastreabilidade
  (`linhas_relacionadas_reee_sinir.csv`), sem forçar um esquema de colunas.

Ajustes feitos para integrar ao projeto:

* os ZIPs vêm da coleta (`coleta.py`) ou de arquivos salvos à mão em
  data/raw/sinir/, em vez de uma pasta `raw/` própria;
* "ó" e "õ" entram nos termos de busca (há "LIXO ELETRÕNICO" nos dados);
* pastas `__MACOSX` são ignoradas e os nomes de arquivo com acentos são
  decodificados (`coleta._nome_no_zip`);
* cada linha candidata recebe a classificação do projeto
  (`planos_sinir.classificar`), porque a busca por palavra-chave é ampla de
  propósito: "eletrônic" também encontra "pregão eletrônico", e "logística
  reversa" encontra pneus, embalagens etc.

Ano de exercício Y refere-se, em geral, ao ano de referência Y-1 no módulo.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Callable

import pandas as pd

from . import config as C

log = logging.getLogger("reee.etl_sinir")

# Links diretos do portal do SINIR (lista do etl_sinir.py da equipe).
URLS = {
    2019: "https://portal-api.sinir.gov.br/wp-content/uploads/2024/07/EstadosMunicipios2019.zip",
    2020: "https://portal-api.sinir.gov.br/wp-content/uploads/2024/07/EstadosMunicipios2020.zip",
    2021: "https://portal-api.sinir.gov.br/wp-content/uploads/2024/06/EstadosMunicipios2021.zip",
    2022: "https://portal-api.sinir.gov.br/wp-content/uploads/2024/06/EstadosMunicipios2022.zip",
    2023: "https://portal-api.sinir.gov.br/wp-content/uploads/2024/07/EstadosMunicipios2023.zip",
    2024: "https://portal-api.sinir.gov.br/wp-content/uploads/2024/07/EstadosMunicipios2024.zip",
    2025: "https://portal-api.sinir.gov.br/wp-content/uploads/2025/09/EstadosMunicipios2025.zip",
}

# Termos do script original; acrescentados "ó" e "õ" porque há grafias como "LIXO ELETRÕNICO" nos dados de 2025.
KEYWORDS = re.compile(r"eletro|eletr[oôóõ]nic|equipamento.*el[eé]tric|log[ií]stica.*reversa|"
                      r"eco\s?-?ponto|\bPEVs?\b|ponto.{0,4}de.{0,4}entrega.{0,4}volunt", re.I)  # + pontos de entrega (objeto do painel)

Progresso = Callable[[str], None]


def _ler_csv(bruto: bytes) -> pd.DataFrame | None:
    for enc in ("utf-8", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(bruto), dtype=str, sep=None, engine="python", encoding=enc)
        except Exception:  # noqa: BLE001
            continue
    return None


def _linhas_candidatas(df: pd.DataFrame) -> pd.DataFrame | None:
    mask = df.astype(str).apply(lambda s: s.str.contains(KEYWORDS, na=False)).any(axis=1)
    if mask.any() or any(KEYWORDS.search(str(c)) for c in df.columns):
        return df.loc[mask].copy() if mask.any() else df.copy()
    return None


def read_tabular_from_zip(zip_path: Path, year: int) -> tuple[list, list]:
    """Inventário e linhas candidatas de um ZIP (lógica do script original)."""
    from .coleta import _nome_no_zip
    inventory, matches = [], []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = _nome_no_zip(info)
            if info.is_dir() or name.startswith("__MACOSX/") or "/._" in "/" + name:
                continue
            low = name.lower()
            try:
                if low.endswith((".xlsx", ".xls")):
                    xls = pd.ExcelFile(io.BytesIO(z.read(info)))
                    for sheet in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
                        inventory.append([year, name, sheet, len(df), len(df.columns)])
                        m = _linhas_candidatas(df)
                        if m is not None:
                            m["__ano_exercicio"], m["__arquivo"], m["__aba"] = year, name, sheet
                            matches.append(m)
                elif low.endswith(".csv"):
                    df = _ler_csv(z.read(info))
                    if df is not None:
                        inventory.append([year, name, "CSV", len(df), len(df.columns)])
                        m = _linhas_candidatas(df)
                        if m is not None:
                            m["__ano_exercicio"], m["__arquivo"], m["__aba"] = year, name, "CSV"
                            matches.append(m)
            except Exception as e:  # noqa: BLE001
                inventory.append([year, name, f"ERRO: {e}", 0, 0])
    return inventory, matches


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    def norm(c):
        c = str(c).strip().lower()
        return re.sub(r"[^\w]+", "_", c, flags=re.UNICODE).strip("_")
    out = df.copy()
    # nomes diferentes podem virar o mesmo ("Meta - Programa" e "Meta Programa" -> meta_programa);
    # colunas repetidas impedem juntar os anos, então as seguintes ganham _2, _3...
    vistos: dict[str, int] = {}
    nomes = []
    for c in out.columns:
        n = norm(c) or "coluna"
        vistos[n] = vistos.get(n, 0) + 1
        nomes.append(n if vistos[n] == 1 else f"{n}_{vistos[n]}")
    out.columns = nomes
    return out


def classificar_linha(linha: pd.Series) -> tuple[str, str, str]:
    """Classificação do projeto para uma linha candidata: (classe, coluna, trecho)."""
    from .planos_sinir import cita_pev, classificar
    lr_col = pev_col = ""
    for c, v in linha.items():
        if str(c).startswith("ano_exercicio") or c in ("arquivo", "aba") or not isinstance(v, str) or not v.strip():
            continue
        reee, lr, trecho = classificar(v)
        if reee:
            return "cita eletroeletrônicos", str(c), trecho
        if lr and not lr_col:
            lr_col = str(c)
        if not pev_col and cita_pev(v)[0]:
            pev_col = str(c)
    if pev_col:
        return "prevê ecoponto/PEV (ponto de entrega)", pev_col, ""
    if lr_col:
        return "só logística reversa (outros resíduos)", lr_col, ""
    return "falso positivo (ex.: pregão eletrônico)", "", ""


def read_tabular_from_dir(pasta: Path, year: int) -> tuple[list, list]:
    """Mesma lógica de read_tabular_from_zip, para anos que só existem extraídos (ex.: RAR de 2025)."""
    inventory, matches = [], []
    for arq in sorted(pasta.rglob("*")):
        if not arq.is_file() or "__MACOSX" in arq.parts or arq.name.startswith("._"):
            continue
        name, low = str(arq.relative_to(pasta)).replace("\\", "/"), arq.name.lower()
        try:
            if low.endswith((".xlsx", ".xls")):
                xls = pd.ExcelFile(arq)
                abas = [(s, pd.read_excel(xls, sheet_name=s, dtype=str)) for s in xls.sheet_names]
            elif low.endswith(".csv"):
                df = _ler_csv(arq.read_bytes())
                abas = [("CSV", df)] if df is not None else []
            else:
                continue
            for aba, df in abas:
                inventory.append([year, name, aba, len(df), len(df.columns)])
                m = _linhas_candidatas(df)
                if m is not None:
                    m["__ano_exercicio"], m["__arquivo"], m["__aba"] = year, name, aba
                    matches.append(m)
        except Exception as e:  # noqa: BLE001
            inventory.append([year, name, f"ERRO: {e}", 0, 0])
    return inventory, matches


def zips_disponiveis() -> dict[int, Path]:
    """ZIPs oficiais já baixados pela coleta ou salvos à mão em data/raw/sinir/."""
    from . import coleta
    achados: dict[int, Path] = {}
    for pasta in (coleta.DIR_DOWNLOAD, C.RAW_SINIR, coleta.DIR_EXTRAIDO):
        if not pasta.exists():
            continue
        for arq in sorted(pasta.iterdir()):
            if arq.is_file() and arq.suffix.lower() == ".zip" and zipfile.is_zipfile(arq):
                anos = re.findall(r"20\d{2}", arq.name)
                if anos and C.ANO_INICIAL <= int(anos[-1]) <= C.ANO_FINAL:
                    achados.setdefault(int(anos[-1]), arq)
    return dict(sorted(achados.items()))


def executar(progresso: Progresso = log.info, zips: dict[int, Path] | None = None) -> dict:
    """Roda o ETL sobre os ZIPs disponíveis e grava o inventário e as linhas candidatas."""
    from . import coleta
    fontes: dict[int, Path] = dict(zips) if zips is not None else zips_disponiveis()
    if zips is None:  # anos sem ZIP (ex.: 2025 baixado em RAR) entram pela pasta já extraída
        for ano in range(C.ANO_INICIAL, C.ANO_FINAL + 1):
            pasta = coleta.DIR_EXTRAIDO / str(ano)
            if ano not in fontes and pasta.is_dir():
                fontes[ano] = pasta
    zips = dict(sorted(fontes.items()))
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    if not zips:
        progresso("ETL do SINIR: nenhum ZIP oficial disponível (rode com --coletar ou salve os ZIPs em data/raw/sinir/)")
        return {"anos": [], "linhas": 0}
    all_inventory, all_matches = [], []
    for year, p in zips.items():
        inv, mats = read_tabular_from_dir(p, year) if p.is_dir() else read_tabular_from_zip(p, year)
        all_inventory.extend(inv)
        all_matches.extend(mats)
        progresso(f"ETL do SINIR {year}: {len(inv)} arquivo(s)/aba(s), "
                  f"{sum(len(m) for m in mats)} linha(s) candidata(s)")
    pd.DataFrame(all_inventory, columns=["ano_exercicio", "arquivo", "aba", "linhas", "colunas"]).to_csv(
        C.PROCESSED / "inventario_arquivos_sinir.csv", index=False, encoding="utf-8-sig")
    resumo = {"anos": sorted(zips), "linhas": 0, "por_classe": {}}
    destino = C.PROCESSED / "linhas_relacionadas_reee_sinir.csv"
    if all_matches:
        reee = pd.concat([normalize_columns(x) for x in all_matches], ignore_index=True, sort=False)
        cls = reee.apply(classificar_linha, axis=1, result_type="expand")
        reee.insert(0, "classificacao_projeto", cls[0])
        reee.insert(1, "coluna_da_mencao", cls[1])
        reee.insert(2, "trecho", cls[2])
        reee.to_csv(destino, index=False, encoding="utf-8-sig")
        resumo["linhas"] = int(len(reee))
        resumo["por_classe"] = {f"{int(a)}": g.value_counts().to_dict()
                                for a, g in reee.groupby("ano_exercicio")["classificacao_projeto"]}
        progresso(f"ETL do SINIR: {len(reee):,} linhas candidatas relacionadas a REEE".replace(",", "."))
    else:
        destino.unlink(missing_ok=True)
        progresso("ETL do SINIR: nenhuma linha relacionada a REEE encontrada automaticamente")
    return resumo
