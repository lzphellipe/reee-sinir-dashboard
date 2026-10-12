"""ETL do SINIR da equipe (etl_sinir.py): inventário, linhas candidatas e classificação."""
import zipfile

import pandas as pd

from reee import config as C, etl_sinir


def test_etl_inventario_linhas_e_classificacao(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PROCESSED", tmp_path / "proc")
    z = tmp_path / "EstadosMunicipios2025.zip"
    csv = ("Ano;Município Declarante;UF Declarante;Solução\n"
           "2025;Capetinga;MG;LIXO ELETRÕNICO\n"
           "2025;Mariana;MG;Contrato por pregão eletrônico 12/2024\n"
           "2025;Jacuí;MG;Logística reversa de pneus\n"
           "2025;Passos;MG;Coleta seletiva\n")
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("EstadosMunicipios2025/Municipal - Solucoes Compartilhadas e Custos.csv", csv.encode("latin-1"))
        f.writestr("__MACOSX/EstadosMunicipios2025/._lixo.csv", b"x")
    resumo = etl_sinir.executar(progresso=lambda m: None, zips={2025: z})
    inv = pd.read_csv(tmp_path / "proc" / "inventario_arquivos_sinir.csv")
    assert len(inv) == 1 and inv["linhas"].iloc[0] == 4          # __MACOSX ignorado
    linhas = pd.read_csv(tmp_path / "proc" / "linhas_relacionadas_reee_sinir.csv")
    assert len(linhas) == 3                                     # "Coleta seletiva" não é candidata
    cls = dict(zip(linhas["município_declarante"], linhas["classificacao_projeto"]))
    assert cls["Capetinga"] == "cita eletroeletrônicos"
    assert cls["Mariana"].startswith("falso positivo")          # pregão eletrônico
    assert cls["Jacuí"].startswith("só logística reversa")
    assert resumo["por_classe"]["2025"]["cita eletroeletrônicos"] == 1


def test_colunas_que_viram_o_mesmo_nome_e_ano_so_extraido(tmp_path, monkeypatch):
    """Anos antigos têm "Meta - Programa" e "Meta Programa"; 2025 pode vir em RAR (só a pasta extraída)."""
    from reee import coleta
    monkeypatch.setattr(C, "PROCESSED", tmp_path / "proc")
    monkeypatch.setattr(C, "RAW_SINIR", tmp_path / "sinir")
    monkeypatch.setattr(coleta, "DIR_DOWNLOAD", tmp_path / "sinir" / "_download")
    monkeypatch.setattr(coleta, "DIR_EXTRAIDO", tmp_path / "sinir" / "extraido")
    z = tmp_path / "sinir" / "EstadosMunicipios2021.zip"
    z.parent.mkdir(parents=True)
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("m.csv", "Município;Meta - Programa;Meta Programa\nA;lixo eletrônico;x\n")
    pasta25 = tmp_path / "sinir" / "extraido" / "2025" / "EstadosMunicipios2025"
    pasta25.mkdir(parents=True)
    (pasta25 / "Municipal - Solucoes.csv").write_text("Município;Solução\nB;Logística reversa de eletroeletrônicos\n", encoding="utf-8")
    resumo = etl_sinir.executar(progresso=lambda m: None)
    assert resumo["anos"] == [2021, 2025]
    linhas = pd.read_csv(tmp_path / "proc" / "linhas_relacionadas_reee_sinir.csv")
    assert {"meta_programa", "meta_programa_2"} <= set(linhas.columns)
    assert (linhas["classificacao_projeto"] == "cita eletroeletrônicos").sum() == 2
