# Objetivo I — Mapeamento conceitual

> Logística reversa de REEE, cidades inteligentes, e-Democracia aplicada ao controle social de resíduos e o papel da Ciência de Dados.

Este documento resume a seção 3 do TCC e mostra **como cada conceito vira uma funcionalidade do painel**. As referências citadas no TCC estão na lista final do próprio trabalho; aqui ficam as que sustentam as decisões do protótipo.

## 1. Mapa conceitual

```mermaid
flowchart LR
  subgraph LR["Logística reversa de REEE"]
    PNRS["PNRS – Lei 12.305/2010<br/>responsabilidade compartilhada"]
    DEC["Decreto 10.240/2020<br/>pontos de recebimento e metas"]
    SLR["Sistemas de LR<br/>entidades gestoras"]
    SINIR["SINIR<br/>relatórios anuais e cadastro de pontos"]
  end
  subgraph CI["Cidades inteligentes"]
    DADOS["Decisão orientada por dados"]
    IND["Indicadores urbanos<br/>(ISO 37120 / 37122)"]
    CARTA["Carta Brasileira para<br/>Cidades Inteligentes"]
  end
  subgraph ED["e-Democracia"]
    TRANSP["Transparência ativa – LAI"]
    ABERTOS["Dados abertos"]
    EPART["e-Participação<br/>informar · consultar · co-decidir"]
    CONTROLE["Controle social"]
  end
  PNRS --> DEC --> SLR --> SINIR
  SINIR -->|"dados brutos"| ETL["Pipeline Python/Pandas"]
  ETL --> DASH(("Dashboard<br/>gestor e cidadão"))
  DADOS --> DASH
  IND --> DASH
  CARTA --> DASH
  TRANSP --> DASH
  ABERTOS --> DASH
  EPART --> DASH
  DASH -->|"gestor"| PLAN["Planejamento de pontos de coleta"]
  DASH -->|"cidadão"| CONTROLE
```

## 2. Logística reversa de REEE

**Logística reversa** é definida na Política Nacional de Resíduos Sólidos (Lei nº 12.305/2010, art. 3º, XII) como o conjunto de ações para coletar e devolver resíduos ao setor empresarial, para reaproveitamento ou destinação ambientalmente adequada. O art. 33 torna o sistema obrigatório para produtos eletroeletrônicos e seus componentes, sob **responsabilidade compartilhada** entre fabricantes, importadores, distribuidores, comerciantes, consumidores e poder público.

**Linhas de produtos.** O estudo da ABDI (2013) agrupa os eletroeletrônicos de uso doméstico em quatro linhas: verde (informática e comunicação), branca (grandes eletrodomésticos), marrom (áudio e vídeo) e azul (eletroportáteis e ferramentas). Os relatórios das entidades não separam pontos nem massa por linha, por isso o painel não faz essa divisão.

**REEE** (resíduos de equipamentos eletroeletrônicos) são os produtos que dependem de corrente elétrica ou campo eletromagnético e chegaram ao fim da vida útil. Concentram metais com valor econômico (cobre, ouro, terras-raras) e substâncias perigosas (chumbo, mercúrio, retardantes de chama), o que os torna prioritários tanto para a economia circular quanto para a saúde pública.

**Marco regulatório** (o recorte do painel é 2023–2025; os anos anteriores dão o contexto):

| Ano | Marco | Efeito para o estudo |
|---|---|---|
| 2010 | PNRS (Lei 12.305) e SINIR | Obrigação de LR e criação do sistema nacional de informações |
| 2019 | Acordo Setorial de Eletroeletrônicos | Início formal do sistema coletivo (fase 1: estruturação) |
| 2020 | Decreto 10.240 | Regras operacionais, pontos de recebimento e metas progressivas |
| 2021–2025 | Fase 2 do Decreto | Metas anuais de municípios atendidos e de peso coletado |
| 2022 | Decreto 10.936 | Nova regulamentação da PNRS, reforça o SINIR |
| 2023 | Decreto 11.413 | Certificado de Crédito de Reciclagem de Logística Reversa (substitui o Recicla+, Decreto 11.044/2022) |
| 2024 | Portaria GM/MMA 1.011 | Modelo padrão do relatório anual de resultados publicado no SINIR |
| 2026 | Portaria GM/MMA 1.560 (2/1/2026) | Mantém para 2026 as metas de 2025 do Decreto 10.240 |

Fluxo operacional previsto no Decreto 10.240/2020, que o dashboard modela nas etapas 1 e 2:

1. descarte pelo consumidor em **ponto de recebimento**;
2. recebimento e armazenamento temporário (ponto de recebimento ou de **consolidação**);
3. transporte até o ponto de consolidação, quando necessário;
4. destinação final ambientalmente adequada (reciclagem, recuperação ou disposição).

**Regra de cobertura usada no protótipo** (`src/reee/config.py`): pelo art. 48, § 2º, cada município da lista do Anexo III ("Municípios alvo") deve ter ao menos 1 ponto de recebimento a cada 25 mil habitantes. O Decreto não fixa um corte populacional; como a lista reúne os cerca de 400 municípios mais populosos (descritos pelas entidades gestoras como os de mais de 80 mil habitantes), o protótipo usa o corte de 80 mil habitantes como aproximação. As metas do Anexo II, anuais e não cumulativas (art. 49), são: 2021, 24 cidades e 1 % do peso; 2022, 68 e 3 %; 2023, 186 e 6 %; 2024, 294 e 12 %; 2025, 400 e 17 %, sobre o peso dos produtos colocados no mercado em 2018 (conferido no texto oficial em 11/10/2026).

**Atores.** Entidade gestora é a pessoa jurídica criada por fabricantes e importadores para estruturar, implementar e operar o sistema de logística reversa (Decreto 10.240/2020, art. 3º, VII); os relatórios publicados no SINIR são da ABREE e da Green Eletron. As entidades prestam informações ao Sinir (art. 30) e enviam relatório anual de desempenho ao MMA (art. 20, X). Elas organizam os sistemas coletivos; empresas podem manter sistemas individuais. Os municípios não são os responsáveis legais pela LR, mas podem firmar termos de cooperação (cedendo espaço para pontos, por exemplo) e são cobrados pela população quando o sistema falha. Daí a importância de um instrumento municipal de acompanhamento.

## 3. Cidades inteligentes

A literatura converge em três dimensões de cidade inteligente: **tecnologia** (infraestrutura de dados), **gestão** (decisão orientada por evidências) e **pessoas** (participação e capital humano). O protótipo se apoia nas duas últimas:

- **Indicadores urbanos padronizados.** A ISO 37120 (cidades sustentáveis) e a ISO 37122 (cidades inteligentes) incluem indicadores de resíduos sólidos, como percentual reciclado e resíduos perigosos tratados. O protótipo adota a mesma lógica de indicador normalizado por população (pontos por 100 mil hab., kg/hab.).
- **Carta Brasileira para Cidades Inteligentes (2020).** Recomenda transformação digital com inclusão, governança de dados e uso de dados abertos, o que orienta a separação entre visão do gestor e visão do cidadão.
- **Painéis urbanos (urban dashboards).** Ferramentas de apoio à decisão que agregam dados heterogêneos em indicadores visuais. A crítica recorrente é que painéis "tecnocráticos" informam o gestor e excluem o cidadão. Separar a visão do gestor da visão do cidadão responde a essa crítica. Kitchin, Lauriault e McArdle (2015) lembram ainda que indicadores e painéis não são neutros: por isso o protótipo mostra a origem de cada número, as lacunas e a fórmula de cada indicador.

## 4. e-Democracia e controle social de resíduos

**e-Democracia** é o uso de tecnologias digitais para ampliar a participação dos cidadãos nas decisões públicas. A **e-participação** costuma ser descrita em níveis crescentes (modelo usado na pesquisa de governo eletrônico da ONU):

| Nível | Significado | Como o dashboard atende |
|---|---|---|
| e-informação | O governo disponibiliza dados | Mapa, indicadores e dados abertos para download |
| e-consulta | O cidadão opina | Formulário de sugestões e correções |
| e-decisão | O cidadão influencia a decisão | Sugestões de local alimentam o ranking de prioridade (trabalho futuro) |

**Base legal da transparência:** Lei de Acesso à Informação (Lei 12.527/2011, transparência ativa no art. 8º), Política de Dados Abertos do Executivo Federal (Decreto 8.777/2016) e Lei do Governo Digital (Lei 14.129/2021). **Controle social** é a fiscalização da gestão pública pela sociedade. Aplicado a resíduos, significa permitir que o morador verifique se a cidade tem pontos suficientes, compare com cidades vizinhas e cobre quem é responsável.

## 5. Dos conceitos aos requisitos

| Conceito | Requisito do protótipo | Onde está |
|---|---|---|
| Responsabilidade compartilhada | Mostrar entidade gestora e tipo de ponto | Gestor › "Pontos por entidade gestora" |
| Metas do Decreto 10.240 | Comparar municípios atendidos com a meta anual | Gestor › gráfico "x meta" e KPI |
| Densidade mínima de pontos | Calcular déficit por município | Gestor › KPI, mapa e ranking |
| Decisão orientada por dados | Índice de prioridade (50 % demanda + 50 % sinais do SINIR) e simulador | Gestor › "Onde instalar os próximos pontos" |
| Indicador normalizado | Pontos/100 mil hab., kg/hab., % pop. coberta | Seletor de indicador do mapa |
| Transparência ativa | Linguagem simples sobre a situação da cidade | Cidadão › ficha do município |
| Dados abertos | CSVs tratados e dicionário de dados | Aba "Dados abertos" |
| e-Consulta | Formulário de contribuição | Cidadão › "Participe" |
| Qualidade da informação | Relatório do que foi limpo/descartado | Dados abertos › "Qualidade dos dados" |

## 6. Ciência de Dados aplicada (seção 3.6 do TCC)

| Conceito | Autor | No protótipo |
|---|---|---|
| Processo KDD: seleção, pré-processamento, transformação, mineração, interpretação | Fayyad, Piatetsky-Shapiro e Smyth (1996) | `coleta.py` → `adaptador_sinir.py`/`relatorios.py` → `indicators.py`/`prioridade_sinir.py` → painel |
| Manipulação reprodutível de dados tabulares em Python | McKinney (2010) | Todo o tratamento em Pandas, com 66 testes automatizados |
| Indicador como síntese que apoia a decisão | Bellen (2005) | Quadro 2 do TCC: cobertura, déficit, per capita, planos com REEE, índice |
| Indicadores e dashboards urbanos não são neutros | Kitchin, Lauriault e McArdle (2015) | Selos de fonte, lacunas declaradas, fórmulas no dicionário |
| Dados abertos ampliam transparência e reuso | Silva et al. (2014) | Aba Dados abertos: CSVs, dicionário, proveniência |
| Sustentabilidade computacional | Gomes et al. (2019) | Ranking de prioridade e simulador de novos pontos |

## 7. Referências

Conferidas em 11/10/2026 e de novo em 12/10/2026 (existência, autores, ano e veículo).

- ABNT. NBR ISO 37120:2021: cidades e comunidades sustentáveis — indicadores para serviços urbanos e qualidade de vida. Rio de Janeiro: ABNT, 2021. (substitui a edição de 2017)
- ABNT. NBR ISO 37122:2020: cidades e comunidades sustentáveis — indicadores para cidades inteligentes. Rio de Janeiro: ABNT, 2020.
- AGÊNCIA BRASILEIRA DE DESENVOLVIMENTO INDUSTRIAL (ABDI). *Logística reversa de equipamentos eletroeletrônicos*: análise de viabilidade técnica e econômica. Brasília, DF: ABDI, 2013.
- ARNSTEIN, S. R. A ladder of citizen participation. *Journal of the American Institute of Planners*, v. 35, n. 4, p. 216-224, 1969.
- BALDÉ, C. P. et al. *Global E-waste Monitor 2024*. Genebra/Bonn: ITU; UNITAR, 2024.
- BRASIL. Lei nº 12.305, de 2 de agosto de 2010 (PNRS).
- BRASIL. Lei nº 12.527, de 18 de novembro de 2011 (LAI).
- BRASIL. Decreto nº 8.777, de 11 de maio de 2016 (Política de Dados Abertos do Poder Executivo federal).
- BRASIL. Decreto nº 10.240, de 12 de fevereiro de 2020 (art. 48, § 2º; Anexos II e III).
- BRASIL. Ministério do Desenvolvimento Regional. *Carta Brasileira para Cidades Inteligentes*. Brasília, DF: MDR, 2020.
- BRASIL. Lei nº 14.129, de 29 de março de 2021 (Governo Digital).
- BRASIL. Decreto nº 10.936, de 12 de janeiro de 2022 (regulamenta a PNRS).
- BRASIL. Decreto nº 11.413, de 13 de fevereiro de 2023 (certificados de crédito de reciclagem).
- BRASIL. Ministério do Meio Ambiente e Mudança do Clima. Portaria GM/MMA nº 1.011, de 11 de março de 2024.
- BRASIL. Ministério do Meio Ambiente e Mudança do Clima. Portaria GM/MMA nº 1.560, de 2 de janeiro de 2026. *Diário Oficial da União*, 5 jan. 2026.
- BELLEN, H. M. van. *Indicadores de sustentabilidade*: uma análise comparativa. Rio de Janeiro: Editora FGV, 2005.
- FAYYAD, U.; PIATETSKY-SHAPIRO, G.; SMYTH, P. From data mining to knowledge discovery in databases. *AI Magazine*, v. 17, n. 3, p. 37-54, 1996.
- GIL, A. C. *Métodos e técnicas de pesquisa social*. 6. ed. São Paulo: Atlas, 2008.
- GOMES, C. et al. Computational sustainability: computing for a better world and a sustainable future. *Communications of the ACM*, v. 62, n. 9, p. 56-65, 2019. DOI: 10.1145/3339399.
- KITCHIN, R.; LAURIAULT, T. P.; MCARDLE, G. Knowing and governing cities through urban indicators, city benchmarking and real-time dashboards. *Regional Studies, Regional Science*, v. 2, n. 1, p. 6-28, 2015.
- LEITE, P. R. *Logística reversa: meio ambiente e competitividade*. 2. ed. São Paulo: Pearson Prentice Hall, 2009. (confira se a cópia consultada é outra edição)
- MACINTOSH, A. Characterizing e-participation in policy-making. In: HAWAII INTERNATIONAL CONFERENCE ON SYSTEM SCIENCES, 37., 2004. *Proceedings* [...]. IEEE, 2004. DOI: 10.1109/HICSS.2004.1265300.
- MCKINNEY, W. Data structures for statistical computing in Python. In: PYTHON IN SCIENCE CONFERENCE, 9., 2010, Austin. *Proceedings* [...]. p. 56-61. DOI: 10.25080/Majora-92bf1922-00a.
- UNITED NATIONS. *E-Government Survey 2024*. New York: UN DESA, 2024.
