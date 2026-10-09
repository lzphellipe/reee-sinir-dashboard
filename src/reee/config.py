"""Configurações centrais do pipeline REEE/SINIR.

Tudo que é parâmetro de negócio (anos, metas legais, mapeamento de colunas)
fica aqui, para que o restante do código não tenha "números mágicos".
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_SINIR = RAW / "sinir"
RAW_IBGE = RAW / "ibge"
RAW_GEO = RAW / "geo"
RAW_DEMO = RAW / "demo"
PROCESSED = DATA / "processed"
POWERBI = PROCESSED / "powerbi"
DASHBOARD_DATA = ROOT / "dashboard" / "data"

# ---------------------------------------------------------------------------
# Recorte temporal do estudo
# ---------------------------------------------------------------------------
ANO_INICIAL = 2019
ANO_FINAL = 2025
ANOS = list(range(ANO_INICIAL, ANO_FINAL + 1))

# ---------------------------------------------------------------------------
# Parâmetros do Decreto nº 10.240/2020 (logística reversa de eletroeletrônicos
# de uso doméstico). CONFERIR no texto oficial (Anexo I) antes de citar no TCC.
# ---------------------------------------------------------------------------
# Obrigação de pontos de recebimento: municípios com mais de 80 mil habitantes,
# com ao menos 1 ponto para cada 25 mil habitantes.
LIMIAR_POPULACIONAL = 80_000
HAB_POR_PONTO_DECRETO = 25_000

# Fase 2 – metas progressivas (ano: (nº acumulado de municípios atendidos,
# % em peso dos produtos colocados no mercado em 2018)).
METAS_DECRETO = {
    2021: {"municipios": 24, "percentual_peso": 1},
    2022: {"municipios": 72, "percentual_peso": 3},
    2023: {"municipios": 130, "percentual_peso": 6},
    2024: {"municipios": 240, "percentual_peso": 12},
    2025: {"municipios": 400, "percentual_peso": 17},
}

# ---------------------------------------------------------------------------
# População por UF – Censo Demográfico 2022 (IBGE). Usada só para calibrar os
# dados de demonstração. Conferir em SIDRA/IBGE (tabela 4709) antes de citar.
# ---------------------------------------------------------------------------
POP_UF_CENSO_2022 = {
    "RO": 1_581_196, "AC": 830_018, "AM": 3_941_613, "RR": 636_707,
    "PA": 8_120_131, "AP": 733_759, "TO": 1_511_460, "MA": 6_776_699,
    "PI": 3_271_199, "CE": 8_794_957, "RN": 3_302_729, "PB": 3_974_687,
    "PE": 9_058_931, "AL": 3_127_683, "SE": 2_210_004, "BA": 14_141_626,
    "MG": 20_538_718, "ES": 3_833_712, "RJ": 16_055_174, "SP": 44_411_238,
    "PR": 11_444_380, "SC": 7_610_361, "RS": 10_882_965, "MS": 2_757_013,
    "MT": 3_658_649, "GO": 7_056_495, "DF": 2_817_381,
}

# ---------------------------------------------------------------------------
# Mapeamento de colunas: os relatórios/exportações do SINIR e das entidades
# gestoras mudam de layout entre anos. Cada nome canônico aceita vários
# apelidos (comparados após normalização: minúsculas, sem acento, sem
# pontuação).
# ---------------------------------------------------------------------------
ALIASES_PONTOS = {
    "uf": ["uf", "estado", "sigla uf", "sg uf"],
    "municipio": ["municipio", "cidade", "nome municipio", "localidade"],
    "cod_ibge": ["codigo ibge", "cod ibge", "ibge", "cod municipio", "codigo municipio", "geocodigo"],
    "entidade": ["entidade gestora", "entidade", "sistema", "responsavel", "gestora"],
    "tipo": ["tipo de ponto", "tipo", "modalidade", "categoria"],
    "situacao": ["situacao", "status"],
    "data_cadastro": ["data de cadastro", "data cadastro", "inicio operacao", "data inicio", "dt cadastro"],
    "ano": ["ano", "ano referencia", "ano base"],
}

ALIASES_MASSA = {
    "ano": ["ano", "ano referencia", "ano base"],
    "uf": ["uf", "estado", "sigla uf"],
    "municipio": ["municipio", "cidade", "nome municipio"],
    "cod_ibge": ["codigo ibge", "cod ibge", "ibge", "cod municipio", "geocodigo"],
    "toneladas": ["peso recebido t", "peso t", "toneladas", "massa t", "quantidade t",
                  "peso recebido toneladas", "massa coletada t"],
    "kg": ["peso kg", "massa kg", "quantidade kg", "peso recebido kg"],
}

ALIASES_POP = {
    "cod_ibge": ["cod ibge", "codigo ibge", "codigo", "cod municipio", "geocodigo", "cod"],
    "populacao": ["populacao", "pop", "populacao residente", "habitantes", "valor"],
}

# Pesos do índice de prioridade de novos pontos (soma = 1).
PESOS_PRIORIDADE = {
    "deficit": 0.45,          # pontos que faltam para cumprir o decreto
    "pop_descoberta": 0.30,   # habitantes acima da capacidade atual da rede
    "baixa_coleta": 0.15,     # kg/hab abaixo da mediana da UF
    "sem_ponto": 0.10,        # município sem nenhum ponto
}
