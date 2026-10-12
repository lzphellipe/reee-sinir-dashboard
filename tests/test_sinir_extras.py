"""Custos do manejo e passivos ambientais declarados ao SINIR."""
import pandas as pd

from reee import config as C, sinir_extras, transform


def _mun():
    return transform.dim_municipio([pd.read_csv(C.RAW_IBGE / "populacao.csv", dtype=str).assign(_arquivo="p", _ano_arquivo=None)])


def test_custos_por_habitante_e_passivos(tmp_path):
    p = tmp_path / "2025"
    p.mkdir()
    (p / "Municipal - Solucoes Compartilhadas e Custos.csv").write_text(
        "Ano;Município Declarante;UF Declarante;Custo Coleta Convencional;Custo Coleta Seletiva;Custo Disposição Final;Possui Taxa de Cobrança\n"
        "2025;Guaranésia;MG;900000;45000;300000;Sim\n"
        "2025;Guaranésia;MG;900000;45000;300000;Sim\n"          # linha repetida por solução: conta uma vez
        "2025;Passos;MG;999999999999;0;;Não\n", encoding="utf-8")  # valor absurdo e zero: descartados
    (p / "Municipal - Passivo Ambiental.csv").write_text(
        "Ano;Município Declarante;UF Declarante;Possui Passivo Ambiental;Passivo Ambiental - Descritivo\n"
        "2025;Guaranésia;MG;Sim;Antigo lixão\n2025;Guaranésia;MG;Sim;Área degradada\n2025;Passos;MG;Não;\n", encoding="utf-8")
    q = {}
    df = sinir_extras.processar(_mun(), q, pasta=tmp_path).set_index("cod_ibge")
    g = df.loc[3128303]  # Guaranésia
    assert 40 < g["custo_conv_hab"] < 60 and g["taxa"] == 1 and g["n_passivos"] == 2
    ps = df.loc[3147907]  # Passos
    assert pd.isna(ps["custo_conv_hab"]) and pd.isna(ps["custo_sel_hab"]) and ps["passivo"] == 0
    assert q["custo_conv_descartados"] == 1
