"""Testes do caminho de dados reais: extração → adaptador → pipeline.

Como o layout real das planilhas do SINIR varia, o arquivo simulado aqui
reúne os problemas típicos de planilhas governamentais: linhas de título acima
do cabeçalho, cabeçalho agrupado em duas linhas, código IBGE de 6 dígitos,
massa em kg num ano e formato pergunta/resposta em outro, ZIP dentro de ZIP e
municípios que não declararam.
"""
import io
import json
import shutil
import zipfile

import numpy as np
import pandas as pd
import pytest

from reee import adaptador_sinir, coleta, config as C


def _base(n=400):
    mun = pd.read_csv(C.RAW_IBGE / "municipios_kelvins.csv")
    return mun.sample(n, random_state=1)[["codigo_ibge", "nome"]].reset_index(drop=True)


def _xlsx_largo(ano, base, kg=False):
    rng = np.random.default_rng(ano)
    linhas = []
    for _, m in base.iterrows():
        tem = rng.random() < 0.4
        n = int(rng.integers(1, 6)) if tem else 0
        massa = round(n * rng.uniform(0.2, 1.5), 3)
        linhas.append([m.codigo_ibge // 10 if ano == 2021 else m.codigo_ibge, m.nome,
                       "Sim" if tem else "Não", n if tem else "", str(massa * (1000 if kg else 1)).replace(".", ","),
                       "Sim", 12.5])
    grupo = ["", "", "Resíduos eletroeletrônicos", "", "", "Coleta seletiva", ""]
    cab = ["Código do Município (IBGE)", "Município",
           "Possui pontos de entrega de eletroeletrônicos?", "Quantidade de PEVs de eletroeletrônicos",
           f"Quantidade coletada de eletroeletrônicos ({'kg' if kg else 't'})", "Possui coleta seletiva?", "Taxa (%)"]
    bruto = [["SINIR – Módulo Estados e Municípios"], [f"Ano de referência {ano}"], [], grupo, cab] + linhas
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(bruto).to_excel(w, sheet_name="Municipios", header=False, index=False)
        pd.DataFrame([["UF", "Total"], ["SP", 10]]).to_excel(w, sheet_name="Estados", header=False, index=False)
    return buf.getvalue()


def _csv_longo(ano, base):
    linhas = ["cod_ibge;municipio;pergunta;resposta"]
    for _, m in base.iterrows():
        linhas.append(f"{m.codigo_ibge};{m.nome};Número de pontos de recebimento de eletroeletrônicos;3")
        linhas.append(f"{m.codigo_ibge};{m.nome};Massa de eletroeletrônicos recebida (toneladas);1,5")
        linhas.append(f"{m.codigo_ibge};{m.nome};Possui aterro sanitário?;Sim")
    return "\n".join(linhas).encode("latin-1")


@pytest.fixture(scope="module")
def arquivos(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("sinir")
    base = _base()
    zips = {}
    for ano in (2021, 2022, 2023):
        z = raiz / f"estadosmunicipios{ano}.zip"
        interno = io.BytesIO()
        with zipfile.ZipFile(interno, "w") as zi:
            if ano == 2023:
                zi.writestr(f"respostas_{ano}.csv", _csv_longo(ano, base.head(150)))
            else:
                zi.writestr(f"Municipios_{ano}.xlsx", _xlsx_largo(ano, base, kg=(ano == 2022)))
        with zipfile.ZipFile(z, "w") as zo:  # ZIP dentro de ZIP
            zo.writestr(f"dados_{ano}.zip", interno.getvalue())
            zo.writestr("LEIAME.txt", "teste")
        zips[ano] = z
    return raiz, zips, base


def test_extrai_zip_aninhado(arquivos, tmp_path):
    _, zips, _ = arquivos
    planilhas = coleta.extrair(zips[2022], tmp_path / "2022")
    assert [p.suffix for p in planilhas] == [".xlsx"]


def test_adaptador_detecta_colunas(arquivos, tmp_path):
    _, zips, base = arquivos
    validos = set(pd.read_csv(C.RAW_IBGE / "municipios_kelvins.csv")["codigo_ibge"])
    for ano in (2021, 2022, 2023):
        coleta.extrair(zips[ano], tmp_path / str(ano))
    decl, inv = adaptador_sinir.processar(validos, tmp_path)
    escolhas = {(r["ano"], c): e["coluna"] for r in inv for c, e in (r.get("escolhas") or {}).items()}
    assert "PEVs" in escolhas[(2022, "pontos")]
    assert "coletada" in escolhas[(2022, "toneladas")]
    assert "Possui pontos" in escolhas[(2022, "possui")]
    assert "pontos" in escolhas[(2023, "pontos")].lower()       # formato longo
    assert set(decl["ano"]) == {2021, 2022, 2023}
    assert decl[decl.ano == 2021]["cod_ibge"].isin(validos).all()  # código de 6 dígitos convertido
    assert len(decl[decl.ano == 2021]) == len(base)
    # kg -> t em 2022: valores comparáveis a 2021
    assert decl[decl.ano == 2022]["toneladas"].max() < 10
    assert (decl[decl.ano == 2023]["pontos"] == 3).all()
    md = adaptador_sinir.salvar_inventario(inv, tmp_path)
    assert "PEVs" in md.read_text(encoding="utf-8")


def test_pipeline_modo_sinir(arquivos, tmp_path, monkeypatch):
    _, zips, base = arquivos
    raw_sinir, raw_ibge = tmp_path / "raw" / "sinir", tmp_path / "raw" / "ibge"
    raw_ibge.mkdir(parents=True)
    for f in ("municipios_kelvins.csv", "estados_kelvins.csv"):
        shutil.copy(C.RAW_IBGE / f, raw_ibge / f)
    pop = pd.read_csv(C.RAW_DEMO / "ibge_populacao_SINTETICA.csv", sep=";")
    pop.iloc[:, [0, 3]].set_axis(["cod_ibge", "populacao"], axis=1).to_csv(raw_ibge / "populacao.csv", index=False)
    for ano, z in zips.items():
        coleta.extrair(z, raw_sinir / "extraido" / str(ano))
    for nome, valor in {"RAW_SINIR": raw_sinir, "RAW_IBGE": raw_ibge, "PROCESSED": tmp_path / "proc",
                        "POWERBI": tmp_path / "proc" / "powerbi", "DASHBOARD_DATA": tmp_path / "dash"}.items():
        monkeypatch.setattr(C, nome, valor)
    shutil.copytree(C.ROOT / "data" / "raw" / "geo", tmp_path / "raw" / "geo")
    monkeypatch.setattr(C, "RAW_GEO", tmp_path / "raw" / "geo")

    from reee.pipeline import executar
    pacote = executar()
    assert pacote["meta"]["fonte"] == "sinir_estados_municipios"
    br = {r["ano"]: r for r in pacote["brasil_ano"]}
    assert br[2019]["municipios_com_info"] == 0          # ano sem arquivo = sem informação
    assert br[2022]["municipios_com_info"] == len(base)
    assert br[2023]["pontos"] == 150 * 3
    # município que não declarou fica sem informação (None), não com zero
    i = pacote["municipios"]["cod"].index(int(base.codigo_ibge.iloc[-1]))
    assert pacote["municipios"]["pontos"][i][4] is None   # 2023, fora dos 150 declarantes
    assert pacote["entidade_ano"] == []
    assert (tmp_path / "proc" / "inventario_sinir.md").exists()
    json.dumps(pacote)  # serializável


def test_planilha_com_textos_numericos_longos(tmp_path):
    """Caso real: células de texto com muitos dígitos (telefones, CNPJ) não podem quebrar a leitura."""
    validos = set(pd.read_csv(C.RAW_IBGE / "municipios_kelvins.csv")["codigo_ibge"])
    linhas = [["Código IBGE", "Município", "Observações", "Quantidade de PEVs de eletroeletrônicos"],
              ["3550308.0", "São Paulo", "Tel (11) 3333-4444; CNPJ 12.345.678/0001-90; " + "9" * 400, "12"],
              ["355030-8", "São Paulo dup", "-", ""],
              ["3.106.200", "Belo Horizonte", "1" * 500, "7"],
              ["texto qualquer", "Sem código", "", "3"]]
    arq = tmp_path / "2024" / "planilha.xlsx"
    arq.parent.mkdir()
    pd.DataFrame(linhas).to_excel(arq, header=False, index=False)
    decl, inv = adaptador_sinir.processar(validos, tmp_path)
    assert not any("erro" in r for r in inv)
    assert inv[0]["coluna_ibge"] == "Código IBGE"
    pts = dict(zip(decl["cod_ibge"], decl["pontos"]))
    assert pts[3550308] == 12 and pts[3106200] == 7
    assert len(decl) == 2


def test_aba_com_erro_nao_derruba_as_demais(tmp_path, monkeypatch):
    validos = set(pd.read_csv(C.RAW_IBGE / "municipios_kelvins.csv")["codigo_ibge"])
    arq = tmp_path / "2024" / "p.xlsx"
    arq.parent.mkdir()
    with pd.ExcelWriter(arq) as w:
        pd.DataFrame([["Código IBGE", "Quantidade de PEVs de eletroeletrônicos"], ["3550308", "5"]]).to_excel(w, sheet_name="ok", header=False, index=False)
        pd.DataFrame([["Código IBGE", "x"], ["3106200", "1"]]).to_excel(w, sheet_name="ruim", header=False, index=False)
    original = adaptador_sinir._montar
    def montar(bruto):
        if bruto.iloc[1, 0] == "3106200":
            raise ValueError("aba corrompida")
        return original(bruto)
    monkeypatch.setattr(adaptador_sinir, "_montar", montar)
    decl, inv = adaptador_sinir.processar(validos, tmp_path)
    assert any(r.get("erro", "").startswith("ValueError") for r in inv)
    assert list(decl["cod_ibge"]) == [3550308]


def test_sem_coluna_de_reee_mantem_relatorios(tmp_path, monkeypatch):
    """Planilhas municipais sem nenhum campo de REEE não podem apagar os dados por UF dos relatórios."""
    raw = tmp_path / "raw"
    (raw / "ibge").mkdir(parents=True)
    for f in ("municipios_kelvins.csv", "estados_kelvins.csv", "populacao.csv"):
        shutil.copy(C.RAW_IBGE / f, raw / "ibge" / f)
    shutil.copytree(C.RAW_GEO, raw / "geo")
    shutil.copytree(C.RAW_SINIR / "relatorios", raw / "sinir" / "relatorios")
    pasta = raw / "sinir" / "extraido" / "2023"
    pasta.mkdir(parents=True)
    pd.DataFrame([["Código IBGE", "Possui aterro sanitário?"], ["3550308", "Sim"]]).to_excel(
        pasta / "m.xlsx", header=False, index=False)
    for nome, valor in {"RAW_SINIR": raw / "sinir", "RAW_IBGE": raw / "ibge", "RAW_GEO": raw / "geo",
                        "PROCESSED": tmp_path / "proc", "POWERBI": tmp_path / "proc" / "powerbi",
                        "DASHBOARD_DATA": tmp_path / "dash"}.items():
        monkeypatch.setattr(C, nome, valor)
    from reee.pipeline import executar
    pacote = executar()
    assert pacote["meta"]["fonte"] == "relatorios_entidades"
    assert {r["ano"]: r for r in pacote["brasil_ano"]}[2022]["pontos"] == 6149
    assert "relatórios das entidades" in pacote["qualidade"]["aviso"]


@pytest.mark.parametrize("nome,flag,esperado", [
    ("Criação de Fonte - 2019.csv".encode("cp850").decode("cp437"), 0, "Criação de Fonte - 2019.csv"),
    ("Fluxo de resíduos - 2021.csv".encode("utf-8").decode("cp437"), 0, "Fluxo de resíduos - 2021.csv"),
    ("Criação já decodificada.csv", 0, "Criação já decodificada.csv"),  # nunca vira "Criaç?o"
    ("Pergunta? \"a\": b|c*.csv", 0x800, "Pergunta_ _a__ b_c_.csv"),
])
def test_nomes_de_arquivo_seguros_no_windows(nome, flag, esperado):
    info = zipfile.ZipInfo("x")
    info.filename, info.flag_bits = nome, flag
    assert coleta._nome_no_zip(info) == esperado
