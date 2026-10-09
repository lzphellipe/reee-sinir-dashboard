# Painel REEE Brasil

Protótipo de dashboard interativo para monitorar a **logística reversa de resíduos de equipamentos eletroeletrônicos (REEE)** no Brasil com dados do **SINIR (2019–2025)**. Serve a dois públicos ao mesmo tempo:

- **Gestor público**: indicadores de cobertura, comparação com as metas do Decreto 10.240/2020, ranking de prioridade e simulador de instalação de novos pontos de coleta.
- **Cidadão**: situação da sua cidade em linguagem simples, como descartar, cidades vizinhas com ponto, formulário de participação e dados abertos.

> ⚠️ **A versão de demonstração usa dados sintéticos** gerados no formato das exportações do SINIR (`src/reee/demo.py`). Os números não descrevem a realidade. Coloque as exportações oficiais em `data/raw/` e rode o pipeline sem `--demo` para substituí-los.

## Objetivos do trabalho e onde cada um está

| Objetivo | Entrega |
|---|---|
| I. Mapear conceitos de LR de REEE, cidades inteligentes e e-Democracia | [`docs/01_referencial_teorico.md`](docs/01_referencial_teorico.md) |
| II. Extrair e tratar dados do SINIR 2019–2025 com Python/Pandas | [`src/reee/`](src/reee) · [`docs/02_metodologia.md`](docs/02_metodologia.md) · [`notebooks/01_exploracao.ipynb`](notebooks/01_exploracao.ipynb) |
| III. Implementar o dashboard (Python, HTML5, CSS3, JS, GitHub; alternativa Power BI) | [`dashboard/`](dashboard) · [`data/processed/powerbi/`](data/processed/powerbi) · [`.github/workflows/pages.yml`](.github/workflows/pages.yml) |
| IV. Avaliar a dupla entrega (gestor e cidadão) | [`docs/03_avaliacao.md`](docs/03_avaliacao.md) + questionário embutido no painel |

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1) gerar dados (sintéticos) e indicadores
PYTHONPATH=src python -m reee.pipeline --demo         # Windows (PowerShell): $env:PYTHONPATH="src"

# 2) testes
python -m pytest

# 3) abrir o painel
cd dashboard && python -m http.server 8000           # http://localhost:8000
```

### Usando dados reais do SINIR

1. Baixe do portal do SINIR as listas de pontos de recebimento de eletroeletrônicos e os relatórios anuais de resultados (2019–2025). Salve em `data/raw/sinir/` com `ponto` no nome dos arquivos de pontos e `massa`/`peso` nos de toneladas (CSV ou XLSX).
2. Baixe a população municipal do IBGE (SIDRA) e salve como `data/raw/ibge/populacao.csv` (colunas com código IBGE e população).
3. Se algum cabeçalho não for reconhecido, adicione o apelido em `src/reee/config.py` (`ALIASES_*`).
4. Rode `PYTHONPATH=src python -m reee.pipeline` e confira `data/processed/qualidade.json`.

## Estrutura

```
├── src/reee/
│   ├── config.py        parâmetros: anos, regras do Decreto, apelidos de colunas, pesos
│   ├── extract.py       leitura tolerante de CSV/XLSX (encoding, separador)
│   ├── transform.py     limpeza, padronização e georreferenciamento por código IBGE
│   ├── indicators.py    indicadores município/UF/Brasil e índice de prioridade
│   ├── export.py        CSVs abertos, modelo Power BI, JSON e GeoJSON do painel
│   ├── demo.py          gerador de dados sintéticos no formato SINIR
│   └── pipeline.py      orquestração (CLI)
├── dashboard/           site estático (index.html, css/, js/, data/)
├── data/raw/            entradas (ibge/, geo/, sinir/, demo/)
├── data/processed/      saídas tratadas + powerbi/ + qualidade.json
├── docs/                referencial, metodologia e avaliação
├── notebooks/           análise exploratória em Pandas
├── scripts/             build de HTML único
└── tests/               testes automatizados (pytest)
```

## Publicação no GitHub Pages

1. Crie o repositório e envie o código (`git push`).
2. Em *Settings › Pages*, escolha **GitHub Actions** como fonte.
3. O workflow `pages.yml` roda os testes, executa o pipeline (com dados reais se houver arquivos em `data/raw/sinir/`, senão com os sintéticos) e publica a pasta `dashboard/`. Ele também roda todo dia 1º do mês para manter os dados atualizados.

## Licença

Código sob licença MIT. Dados de origem pertencem às respectivas fontes (MMA/SINIR, IBGE); a malha das UFs vem do projeto *click_that_hood* e o cadastro de municípios de *kelvins/municipios-brasileiros* (ambos derivados do IBGE).
