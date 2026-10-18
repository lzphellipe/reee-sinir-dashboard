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
ANO_INICIAL = 2023          # recorte do TCC: 2023–2025 (use 2019 para a série histórica completa)
ANO_FINAL = 2025
ANOS = list(range(ANO_INICIAL, ANO_FINAL + 1))
# Anos exibidos no painel (delimitação do TCC); limitados ao recorte ANO_INICIAL–ANO_FINAL.
ANOS_PAINEL = [2023, 2024, 2025]
ANO_BASE = 2023            # linha de base: primeiro ano do recorte (com 2019–2025, use 2022: único ano com ABREE + Green Eletron por UF)
ANO_INICIAL_PAINEL = 2023  # o painel abre neste ano
# Região disponível no filtro (o TCC destaca o Sudeste); "" = abre no Brasil inteiro.
REGIAO_PADRAO = ""

# Linha de produto atendida principalmente por cada entidade gestora (TCC, seção 3.4).
ENTIDADE_LINHA = {"ABREE": "linha branca", "Green Eletron": "linha verde"}

# Localizadores oficiais de pontos de recebimento (o SINIR não publica os endereços).
LOCALIZADORES = {
    "ABREE": "https://abree.org.br/pontos-de-recebimento",
    "Green Eletron": "https://greeneletron.org.br/localizador",
}

# Meta em peso (Decreto 10.240/2020, Anexo II) por entidade. A base é o peso colocado no
# mercado em 2018 pelas empresas de cada sistema, que não é público. Para a Green Eletron
# ela é estimada pela meta de 2024 divulgada (12 % = 8.066,17 t; Abinee, 21/08/2025).
BASE_PESO_2018_T = {"Green Eletron": round(8066.17 / 0.12, 2)}
COLETA_DIVULGADA_T = {  # massa coletada divulgada, quando não está nos relatórios transcritos
    ("Green Eletron", 2024): {"texto": "meta cumprida (valor não divulgado)", "fonte": "Abinee, 21/08/2025"},
    ("Green Eletron", 2025): {"texto": "mais de 12,5 mil t (aproximado)", "fonte": "Green Eletron, 23/04/2026"},
}

# ---------------------------------------------------------------------------
# Parâmetros do Decreto nº 10.240/2020 (logística reversa de eletroeletrônicos
# de uso doméstico). Conferido no texto oficial (planalto.gov.br) em 11/10/2026.
# ---------------------------------------------------------------------------
# Art. 48, § 2º: cada município atendido constante do Anexo III ("Lista dos
# Municípios alvo") instalará no mínimo 1 ponto de recebimento a cada 25 mil
# habitantes. O Decreto não fixa um corte populacional; a lista do Anexo III
# reúne os cerca de 400 municípios mais populosos, e as entidades gestoras a
# descrevem como "municípios com mais de 80 mil habitantes". O protótipo usa
# esse corte como aproximação da lista.
# ---------------------------------------------------------------------------
LIMIAR_POPULACIONAL = 80_000
HAB_POR_PONTO_DECRETO = 25_000

# Anexo II – metas anuais e não cumulativas (art. 49): total de cidades
# atendidas e % em peso dos produtos colocados no mercado em 2018.
METAS_DECRETO = {
    2021: {"municipios": 24, "percentual_peso": 1},
    2022: {"municipios": 68, "percentual_peso": 3},
    2023: {"municipios": 186, "percentual_peso": 6},
    2024: {"municipios": 294, "percentual_peso": 12},
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
    "MG": 20_539_989, "ES": 3_833_712, "RJ": 16_055_174, "SP": 44_411_238,
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

# Índice de prioridade com dados do SINIR (2023–2025), por município-alvo (soma = 1).
# "demanda" = posição do município nos pontos exigidos pelo Decreto (população ÷ 25 mil);
# os demais são sinais de fragilidade (1 = sinal presente; sem informação conta como sinal).
PESOS_PRIORIDADE_SINIR = {
    "demanda": 0.50,
    "sem_pev_listado": 0.15,      # nenhum PEV na lista municipal da Green Eletron
    "sem_plano": 0.10,            # não declarou o plano ao SINIR no ano
    "plano_sem_reee": 0.10,       # plano não cita eletroeletrônicos
    "sem_coleta_seletiva": 0.05,  # não tem coleta seletiva implantada
    "plano_sem_pev": 0.05,        # plano não prevê ecoponto/PEV
    "passivo": 0.05,              # declarou passivo ambiental (lixão, área degradada)
}
CLASSES_PRIORIDADE_SINIR = ((70, "Alta"), (55, "Média"), (0, "Baixa"))  # ~20 % Alta em 2025

# Pesos do índice de prioridade de novos pontos (soma = 1).
PESOS_PRIORIDADE = {
    "deficit": 0.45,          # pontos que faltam para cumprir o decreto
    "pop_descoberta": 0.30,   # habitantes acima da capacidade atual da rede
    "baixa_coleta": 0.15,     # kg/hab abaixo da mediana da UF
    "sem_ponto": 0.10,        # município sem nenhum ponto
}
