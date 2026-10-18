# Painel REEE Brasil

**Onde o Brasil descarta seus eletrônicos, e onde ainda falta lugar para isso.**

Protótipo de dashboard que acompanha a logística reversa de **resíduos de equipamentos eletroeletrônicos (REEE)** com dados do **SINIR (2023–2025)** e do **Censo 2022**. É o protótipo do TCC *Sustentabilidade e logística reversa de Resíduos de Equipamentos Eletroeletrônicos (REEE) no Brasil* (UNIVESP, Ciência de Dados, Grupo 5, 2026). A mesma base de dados atende a dois públicos:

| Para o **gestor público** | Para o **cidadão** |
|---|---|
| Quantos pontos de recebimento existem e quantos a lei exige em cada estado | A situação da sua cidade, em linguagem simples |
| Comparação com as metas do Decreto 10.240/2020 | Cidades vizinhas com ponto de coleta |
| Ranking de onde instalar os próximos pontos | Como descartar e o que é aceito |
| Séries por entidade gestora (ABREE, Green Eletron) | Formulário para sugerir pontos e corrigir dados |

![Python](https://img.shields.io/badge/Python-3.10%2B-1f6f5c) ![Pandas](https://img.shields.io/badge/ETL-Pandas-1f6f5c) ![Front-end](https://img.shields.io/badge/HTML5%20·%20CSS3%20·%20JS-d3%20%2B%20Chart.js-a3531f) ![Testes](https://img.shields.io/badge/testes-66%20passando-0ca30c) ![Licença](https://img.shields.io/badge/licença-MIT-47564f)

---

## O que os dados reais já mostram (2023–2025)

- **A rede cresce acima da meta anual.** Em 2023, a Green Eletron informou **1.282 pontos em 306 municípios** (meta do Decreto: 186). Em 2024, **1.611 pontos em 366 municípios** (meta: 294). A meta de 2025, de 400 municípios, ainda não pode ser verificada: os relatórios de 2025 não foram publicados.
- **Os municípios quase não falam de eletroeletrônicos.** Em 2025, **1.002 municípios** (18 %) declararam dados ao SINIR; só **15 citam REEE** no plano e **51 preveem ecoponto ou PEV**.
- **Onde instalar primeiro.** Dos **405 municípios-alvo** (mais de 80 mil habitantes, aproximação do Anexo III do Decreto), **94 têm prioridade alta** em 2025.
- **O SINIR não publica número de pontos por município.** O módulo Estados e Municípios só traz os planos em texto livre. O painel transforma esses textos num indicador municipal, com o trecho original como evidência.

> Os números de pontos são por estado ou nacionais porque é assim que as entidades publicam. Trocando `ANO_INICIAL` para 2019 em `config.py`, o painel mostra também 2019–2022, incluindo o relatório da ABREE de 2022.

---

## Começo rápido

Você precisa do **Python 3.10 ou mais novo**. Todos os comandos rodam **a partir da pasta raiz do projeto** (onde está este README), nunca de dentro de `src\reee`.

**Windows (PowerShell)**

```powershell
cd C:\Users\PC\Documents\tcc
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python iniciar.py
```

**Linux / macOS**

```bash
cd ~/tcc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python iniciar.py
```

O navegador abre sozinho em **http://localhost:8000**. Na primeira execução, o servidor busca os dados oficiais em segundo plano, e a barra de status no topo do painel mostra cada etapa.

---

## Comandos

| Quero... | Comando |
|---|---|
| Abrir o painel e atualizar os dados se estiverem velhos | `python iniciar.py` |
| Abrir o painel só com os dados que já estão no projeto | `python iniciar.py --sem-atualizar` |
| Usar outra porta | `python iniciar.py --porta 8080` |
| Abrir sem lançar o navegador | `python iniciar.py --sem-navegador` |
| Considerar os dados velhos depois de N dias (padrão: 7) | `python iniciar.py --validade 30` |
| Ver o painel com dados sintéticos, sem internet | `python iniciar.py --demo --sem-atualizar` |
| Baixar e processar os dados oficiais, sem abrir o painel | `python iniciar.py pipeline --coletar` |
| Baixar tudo de novo, ignorando o cache | `python iniciar.py pipeline --coletar --forcar` |
| Reprocessar o que já foi baixado | `python iniciar.py pipeline` |
| Gerar só os dados de demonstração | `python iniciar.py pipeline --demo` |
| Rodar os testes | `python -m pytest` (roda em 2019–2025 qualquer que seja o recorte do `config.py`) |

> **Cuidado com `--demo`.** Ele substitui os dados reais do painel pelos sintéticos. Para voltar aos reais, rode `python iniciar.py pipeline`.

<details>
<summary>Alternativa: instalar o pacote (sem o atalho <code>iniciar.py</code>)</summary>

```powershell
pip install -e .
python -m reee.servidor            # mesmo que python iniciar.py
python -m reee.pipeline --coletar  # mesmo que python iniciar.py pipeline --coletar
```

Depois do `pip install -e .`, os comandos `reee-painel` e `reee-pipeline` também ficam disponíveis no terminal.
</details>

---

## Como funciona

```mermaid
flowchart LR
  A["Portal de dados abertos do MMA<br/>(SINIR, API CKAN)"] -->|ZIP / RAR| C
  B["IBGE / SIDRA<br/>população Censo 2022"] --> C
  R["Relatórios anuais<br/>ABREE · Green Eletron"] --> T
  C["coleta.py<br/>download com cache<br/>e extração"] --> T
  T["adaptador_sinir.py · relatorios.py<br/>acha colunas de REEE<br/>corrige nomes e códigos"] --> I
  I["indicators.py<br/>cobertura, déficit,<br/>prioridade"] --> E
  E["export.py"] --> P["Painel web<br/>(atualiza sozinho)"]
  E --> O["CSVs abertos"]
  E --> BI["Modelo Power BI"]
```

1. **Coleta.** Consulta a API do portal do MMA, baixa os arquivos anuais do SINIR e a população do IBGE. Os downloads ficam em cache e só são refeitos quando o arquivo muda na fonte.
2. **Tratamento.** Lê planilhas com layouts diferentes a cada ano. O pipeline acha a linha de cabeçalho, a coluna de código IBGE e as colunas de eletroeletrônicos. Também converte números no formato brasileiro (`1.234,56`) e corrige nomes de municípios grafados errado (por exemplo, "Guarupuava" → Guarapuava).
3. **Indicadores.** Calcula pontos por 100 mil habitantes, pontos exigidos pela regra do Decreto, déficit, cobertura e índice de prioridade. Município que não informou dados fica **sem informação**, nunca com zero.
4. **Publicação.** Grava o pacote do painel de forma atômica (o painel nunca lê um arquivo pela metade), além dos dados abertos e do relatório de qualidade.

---

## De onde vêm os dados

| Fonte | O que traz | Situação no projeto |
|---|---|---|
| **IBGE – Censo 2022** (SIDRA, tabela 4709) | População dos 5.570 municípios | **Incluída** em `data/raw/ibge/populacao.csv`. A soma é 203.080.756, o total oficial, e cada estado bate com seu total. |
| **ABREE – Relatório 2022** | Pontos 2021/2022, municípios atendidos e toneladas, por estado | **Incluída** em `data/raw/sinir/relatorios/`. Os totais conferem com os impressos no relatório. |
| **Green Eletron – Relatórios 2022 e 2023** | 2022: lista de 266 municípios com seus PEVs. 2023: PEVs e municípios por estado | **Incluída.** Os totais conferem, inclusive os regionais. |
| **ABINEE – notícia de 21/08/2025** | Totais da Green Eletron em 2024: 1.611 PEVs e 366 municípios | **Incluída** em `totais_nacionais.csv` (sem detalhe por estado). |
| **SINIR – Módulo Estados e Municípios** (2023–2025) | Planos de gestão de resíduos declarados por estados e municípios | **Baixada automaticamente** por `python iniciar.py`. Não traz números de REEE; o painel lê os **textos** das metas e soluções e mostra quais municípios citam ações para eletroeletrônicos, com o trecho como evidência. |

A proveniência de cada número (documento, URL e conferência) está em `data/raw/sinir/relatorios/fontes.json` e aparece na aba **Dados abertos** do painel.

**Lacunas conhecidas:**
- **2019 e 2020:** só há totais nacionais da ABREE (16 t e 51 t).
- **2023:** só a Green Eletron publicou. O relatório da ABREE remete os números a um anexo que não foi publicado.
- **2024 e 2025:** nenhum relatório no SINIR até 08/10/2026; 2024 usa os totais da ABINEE.
- **Municípios atendidos:** um município atendido pelas duas entidades conta duas vezes na soma.

---

## Quando o adaptador erra uma coluna

As planilhas do SINIR são declarações dos municípios e mudam de formato a cada ano. Depois de cada coleta, confira o arquivo **`data/processed/inventario_sinir.md`**. Ele lista cada aba lida e a coluna escolhida para cada campo, com uma pontuação de confiança.

Se alguma escolha estiver errada, indique a coluna certa em `data/raw/sinir/mapeamento.json`:

```json
{
  "*":    { "pontos": "Quantidade de PEVs de eletroeletrônicos" },
  "2023": { "toneladas": "Massa coletada de REEE (t)", "cod_ibge": "Cód. Município" }
}
```

A chave `"*"` vale para todos os anos; um ano específico sobrepõe. Depois, rode `python iniciar.py pipeline`.

---

## Problemas comuns

| Mensagem | Causa e solução |
|---|---|
| `ModuleNotFoundError: No module named 'reee'` | O comando foi rodado de dentro de `src\reee`. Volte para a raiz (`cd C:\Users\PC\Documents\tcc`) e use `python iniciar.py`. |
| `ImportError: attempted relative import with no known parent package` | O arquivo foi executado direto (`python pipeline.py`). Use `python iniciar.py pipeline`. |
| `Cannot convert non-finite values (NA or inf) to integer` | Versão antiga do adaptador, que juntava os dígitos de células de texto longas. Atualize `src/reee/adaptador_sinir.py` e `src/reee/utils.py`. |
| `sem acesso a dados.mma.gov.br` | O computador está sem internet ou atrás de um proxy. O painel continua funcionando com os dados já incluídos. |
| `Não foi possível extrair o RAR` | O arquivo de 2025 vem em RAR. Instale o [7-Zip](https://www.7-zip.org/) e rode de novo. |
| A página abre, mas sem gráficos | As bibliotecas d3 e Chart.js vêm de CDN e precisam de internet na primeira abertura. |
| A porta 8000 está ocupada | `python iniciar.py --porta 8080` |

---

## Estrutura

```
├── iniciar.py              atalho: abre o painel ou roda o pipeline, de qualquer pasta
├── src/reee/
│   ├── coleta.py           download: API do MMA (CKAN) e IBGE (SIDRA), cache, ZIP/RAR
│   ├── adaptador_sinir.py  lê as planilhas do SINIR e gera o inventário
│   ├── relatorios.py       relatórios das entidades: conferência e casamento de nomes
│   ├── planos_sinir.py     planos municipais: o texto cita eletroeletrônicos? (com trecho)
│   ├── extract.py          leitura tolerante de CSV/XLSX (encoding, separador)
│   ├── transform.py        limpeza e georreferenciamento por código IBGE
│   ├── indicators.py       indicadores por município, estado e Brasil
│   ├── export.py           dados abertos, Power BI e pacote do painel
│   ├── pipeline.py         orquestra as etapas
│   ├── servidor.py         servidor local com /api/status e /api/atualizar
│   ├── nuvem.py            execução no Azure: Blob Storage, status e pasta temporária
│   ├── demo.py             gerador de dados sintéticos no formato do SINIR
│   └── config.py           anos, regras do Decreto, apelidos de colunas, pesos
├── function_app.py         funções do Azure (painel, status, atualizar, fila, mensal)
├── host.json               configuração do Azure Functions
├── dashboard/              site estático (index.html, css/, js/, data/)
├── data/raw/               entradas: ibge/, geo/, sinir/ (relatorios/, downloads)
├── data/processed/         saídas tratadas, powerbi/, qualidade.json, inventário
├── docs/                   referencial, metodologia, limitações, Azure e pedido LAI
├── notebooks/              análise exploratória em Pandas
└── tests/                  66 testes, incluindo um portal MMA/IBGE simulado e as funções do Azure
```

---

## Recursos do painel

- **Onde instalar os próximos pontos (2023–2025):** índice de 0 a 100 por município-alvo do Decreto, com 50 % de demanda (pontos exigidos) e 50 % de sinais nos dados do SINIR: sem PEV listado, sem plano, plano sem REEE, sem coleta seletiva, plano sem ecoponto/PEV e passivo ambiental. Pesos em `PESOS_PRIORIDADE_SINIR` (`src/reee/config.py`), definidos pelo grupo e ainda sem análise de sensibilidade nem validação com gestores; tabela completa em `prioridade_sinir.csv`.
- **Simulador:** o controle deslizante distribui novos pontos pela ordem do índice e mostra municípios atendidos, quantos passam a cumprir o Decreto e o déficit restante. O déficit é estimado (pontos exigidos − PEVs listados da Green Eletron, 2022), uma estimativa máxima porque a ABREE não publica pontos por município.
- **Link compartilhável:** ano, região, UF, aba, indicador e cidade ficam no endereço (`?ano=2024&uf=MG&aba=cidadao&cidade=3106200`). O botão **Copiar link desta visão** copia o endereço.
- **Busca de município:** autocompletar que ignora acentos e maiúsculas (`sao jose` encontra São José), com setas e Enter.
- **Acessibilidade (WCAG 2.1 AA, conferida com axe-core):** link para pular ao conteúdo, mapa navegável por Tab e Enter, abas com setas, tabela com os números de cada gráfico, avisos para leitor de tela, contraste mínimo de 4,5:1 e respeito à preferência por menos animação.
- **Tema claro/escuro:** segue o sistema até a pessoa escolher; a escolha fica salva no navegador.
- **Filtro de parceria:** no ranking, a caixa "Só municípios cujo plano já prevê ecoponto/PEV e sem PEV listado" mostra os candidatos diretos a parceria com as entidades.
- **Comparar municípios:** até 3 cidades lado a lado na aba Cidadão (plano, REEE, coleta seletiva, custos, passivos, pontos exigidos e índice), também no link (`&comparar=3550308,3128303`).
- **Evolução da cidade:** a ficha mostra, ano a ano (2023–2025), o que a prefeitura declarou ao SINIR e como o índice de prioridade mudou.
- **Ficha em PDF:** o botão **Imprimir ou salvar PDF** gera só a ficha da cidade, com data, link e fontes.
- **Selos de fonte:** cada indicador do topo diz de onde vem o número e de que ano é (relatório da entidade, SINIR, IBGE ou Decreto).
- **Contribuições dos cidadãos:** a aba Gestor resume as sugestões e correções enviadas (por município e as mais recentes), lidas de `contribuicoes.csv`.
- **Pedido de endereços dos pontos:** modelos de pedido pela Lei de Acesso à Informação em [`docs/05_pedido_lai.md`](docs/05_pedido_lai.md).

## Objetivos do trabalho

| Objetivo específico (TCC) | Onde está |
|---|---|
| **I.** Mapear os conceitos de logística reversa de REEE, cidades inteligentes e e-Democracia, e o papel da Ciência de Dados | [`docs/01_referencial_teorico.md`](docs/01_referencial_teorico.md) |
| **II.** Identificar, extrair e tratar os dados do SINIR (2023–2025) com Python e Pandas | [`src/reee/`](src/reee), [`docs/02_metodologia.md`](docs/02_metodologia.md), [`notebooks/01_exploracao.ipynb`](notebooks/01_exploracao.ipynb) |
| **III.** Implementar o dashboard (HTML5, CSS3, JS, D3 e GitHub; Power BI como alternativa) | [`dashboard/`](dashboard), [`data/processed/powerbi/`](data/processed/powerbi), [`.github/workflows/`](.github/workflows) |

O antigo objetivo IV (avaliação com usuários) saiu do escopo do TCC; as limitações e os trabalhos futuros estão em [`docs/03_limitacoes.md`](docs/03_limitacoes.md).

---

## Publicar no GitHub Pages

1. Crie o repositório e envie o código (`git push`).
2. Em **Settings › Pages**, escolha **GitHub Actions** como fonte.
3. O workflow [`pages.yml`](.github/workflows/pages.yml) roda os testes, faz a coleta oficial, trata os dados e publica a pasta `dashboard/`. Ele roda a cada push e todo dia 1º do mês. Se o portal do MMA estiver fora do ar, publica os dados de demonstração e registra um aviso. O inventário das planilhas fica disponível como artefato da execução.

No Pages o painel é estático: a atualização acontece pelo agendamento, e o botão "Atualizar dados" só aparece no servidor local ou no Azure.

## Publicar no Azure Functions

Para ter o painel **com o botão "Atualizar dados" funcionando na internet**, publique no Azure Functions. O mesmo código roda lá sem mudanças no JavaScript:

- `function_app.py` serve o painel e as rotas `/api/status` e `/api/atualizar`;
- o pedido de atualização vai para uma fila, e a coleta roda em segundo plano (sem estourar o tempo limite do HTTP);
- os dados novos ficam no Blob Storage, com os dados empacotados como plano B;
- uma atualização automática roda todo dia 1º.

O workflow [`azure-functions.yml`](.github/workflows/azure-functions.yml) testa, atualiza os dados e publica a cada push na `main`. Ele precisa de:

- um Function App Linux com Python 3.12;
- o secret `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`;
- a variável `AZURE_FUNCTIONAPP_NAME`.

O passo a passo, com os comandos `az`, está em [`docs/04_azure.md`](docs/04_azure.md).

Os dois workflows rodam a cada push. Se for usar só um destino, apague o outro arquivo em `.github/workflows/`.

---

## Antes de citar no TCC

- **Metas do Decreto.** As metas em `src/reee/config.py` seguem o Anexo II do Decreto 10.240/2020 (24, 68, 186, 294 e 400 cidades; 1 %, 3 %, 6 %, 12 % e 17 % do peso), conferidas em 11/10/2026. A Portaria GM/MMA 1.560/2026 manteve para 2026 as metas de 2025. O corte de 80 mil habitantes é uma aproximação da lista de municípios do Anexo III.
- **Contagem não é acesso.** Cumprir o número de pontos não garante acesso: um município pode ter todos os pontos num mesmo bairro.
- **Dados autodeclarados.** As planilhas do módulo municipal do SINIR são preenchidas pelos próprios municípios. O painel mostra quantos municípios informaram em cada ano.

## Licença

Código sob licença MIT. Os dados pertencem às fontes (MMA/SINIR, IBGE, ABREE, Green Eletron). A malha das UFs vem do projeto *click_that_hood* e o cadastro de municípios de *kelvins/municipios-brasileiros*, ambos derivados do IBGE.