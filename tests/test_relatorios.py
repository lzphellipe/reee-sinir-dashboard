"""Dados reais transcritos dos relatórios do SINIR: conferência e casamento de nomes."""
import pandas as pd

from reee import config as C, relatorios, transform


def _mun():
    return transform.dim_municipio([pd.read_csv(C.RAW_IBGE / "populacao.csv", dtype=str).assign(_arquivo="p", _ano_arquivo=None)])


def test_populacao_censo_2022_completa():
    pop = pd.read_csv(C.RAW_IBGE / "populacao.csv")
    assert len(pop) == 5570 and pop["populacao"].sum() == 203_080_756
    assert pop[pop.cod_ibge == 3550308]["populacao"].item() == 11_451_999  # São Paulo
    uf = pop.assign(uf=pop.cod_ibge // 100000).groupby("uf")["populacao"].sum()
    codigos = {11: "RO", 31: "MG", 35: "SP", 53: "DF"}
    for c, sig in codigos.items():
        assert uf[c] == C.POP_UF_CENSO_2022[sig]


def test_relatorios_conferem_e_casam_nomes():
    q = {}
    rel = relatorios.carregar(_mun(), q)
    ue = rel["uf_entidade"]
    assert ue[(ue.ano == 2022) & (ue.entidade == "ABREE")]["pontos"].sum() == 4997
    assert ue[(ue.ano == 2022) & (ue.entidade == "Green Eletron")]["pontos"].sum() == 1152
    assert ue[(ue.ano == 2023) & (ue.entidade == "Green Eletron")]["municipios_atendidos"].sum() == 306
    assert q["relatorio_municipios_nao_casados"] == []
    assert "Guarupuava/PR → Guarapuava" in q["relatorio_municipios_nome_corrigido"]
    assert len(rel["mun_entidade"]) == 266
