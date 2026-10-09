# Objetivo IV — Avaliação da dupla entrega

O protótipo é avaliado por duas lentes, uma para cada público:

| Entrega | Público | Pergunta de avaliação | Natureza |
|---|---|---|---|
| **Eficiência no planejamento** | Gestor público municipal/estadual | O painel reduz o esforço e melhora a qualidade da decisão sobre onde instalar pontos de coleta? | Desempenho em tarefas + análise de cenários |
| **Eficácia na transparência** | Cidadão | O painel permite que qualquer pessoa encontre, entenda, confie e use a informação para exercer controle social? | Checklist normativo + usabilidade + percepção |

## 1. Entrega ao gestor: eficiência no planejamento

### 1.1 Teste de tarefas (comparativo)

Cada participante executa as mesmas tarefas em duas condições, em ordem alternada para controlar aprendizado: **(A)** planilhas brutas do SINIR + IBGE e **(B)** dashboard.

| # | Tarefa | Resposta correta vem de |
|---|---|---|
| T1 | Quantos municípios acima de 80 mil hab. da sua UF não têm ponto de recebimento? | KPI + mapa filtrado |
| T2 | O Brasil atingiu a meta de municípios atendidos do Decreto em 2024? | Gráfico "x meta" |
| T3 | Quais 5 municípios da UF deveriam receber os próximos pontos? | Tabela de prioridade |
| T4 | Com 50 novos pontos, quantos municípios passariam a cumprir o Decreto? | Simulador |
| T5 | Qual entidade gestora opera mais pontos no ano? | Barras por entidade |

**Métricas:** tempo por tarefa (s), taxa de acerto (%), número de arquivos/telas consultados e confiança declarada (1–5). **Hipótese:** em B o tempo cai e o acerto sobe, sobretudo em T3 e T4, que exigem cruzar fontes e calcular déficit.

Sugestão de amostra: 5 a 8 servidores de secretarias de meio ambiente ou de serviços urbanos (amostras pequenas bastam para teste de usabilidade exploratório).

### 1.2 Análise de cenários do simulador

O simulador instala pontos seguindo o índice de prioridade. A tabela abaixo foi gerada com os **dados sintéticos de demonstração**; refaça com dados reais para o trabalho final.

| Novos pontos | Municípios atendidos | Passam a cumprir o Decreto | Pessoas com o 1º ponto na cidade | Déficit restante (de 1.120) |
|---:|---:|---:|---:|---:|
| 100 | 3 | 2 | 0 | 1.020 |
| 300 | 15 | 14 | 187.681 | 820 |
| 500 | 52 | 51 | 187.681 | 620 |
| 1.000 | 353 | 141 | 12.879.942 | 332 |

Leitura: a regra "completar o município mais prioritário antes de seguir" maximiza conformidade legal com poucos pontos, mas demora a levar o primeiro ponto a cidades sem nenhum. Comparar com uma regra alternativa ("1 ponto por cidade sem ponto primeiro") é um bom experimento para discutir equidade x conformidade. Os pesos do índice ficam em `config.py` para análise de sensibilidade (ex.: variar o peso do déficit entre 0,30 e 0,60 e medir quanto o top-20 muda, via correlação de Spearman).

## 2. Entrega ao cidadão: eficácia na transparência

### 2.1 Checklist normativo (LAI, art. 8º, § 3º)

| Requisito da Lei 12.527/2011 | Atende? | Evidência no protótipo |
|---|---|---|
| I – ferramenta de pesquisa de conteúdo | Sim | Busca de município com autocompletar |
| II – gravação de relatórios em formatos abertos e não proprietários | Sim | CSV UTF-8 na aba Dados abertos |
| III – acesso automatizado por sistemas externos (legível por máquina) | Sim | `dashboard.json` e CSVs com dicionário |
| IV – divulgação dos formatos utilizados | Sim | Dicionário de indicadores e `docs/02_metodologia.md` |
| V – garantir autenticidade e integridade | Parcial | Código e dados versionados no GitHub; falta assinatura/hash publicado |
| VI – manter informações atualizadas | Parcial | Data de geração visível; atualização depende de rodar o pipeline (agendável no GitHub Actions) |
| VII – indicar local e instruções de contato | Parcial | Formulário de participação; falta o canal oficial do órgão |
| VIII – acessibilidade para pessoas com deficiência | Parcial | Contraste nos dois temas, rótulos além da cor, teclado; falta auditoria com leitor de tela (eMAG/WCAG) |

### 2.2 Escala de usabilidade (SUS)

Aplicar o *System Usability Scale* (10 itens, 1–5) após o uso livre do painel. Pontuação: itens ímpares valem (nota − 1), pares valem (5 − nota); soma × 2,5 resulta em 0–100. Acima de 68 é considerado acima da média.

### 2.3 Questionário embutido no painel

A aba Cidadão já coleta seis afirmações em escala de 1 a 5, com perfil do respondente (Cidadão, Gestor, Pesquisador). As respostas podem ser copiadas em CSV para análise.

| Item | Dimensão de transparência |
|---|---|
| Q1 Encontrei com facilidade a situação da minha cidade | Encontrabilidade |
| Q2 O mapa e os gráficos são fáceis de entender | Compreensibilidade |
| Q3 Confio na origem e no método dos dados | Confiabilidade |
| Q4 O painel me ajuda a cobrar o poder público | Controle social |
| Q5 O ranking de prioridade ajudaria a planejar novos pontos | Utilidade para decisão |
| Q6 Eu voltaria a usar este painel | Intenção de uso |

Análise sugerida: mediana e distribuição por item, comparação entre perfis (Mann-Whitney), alfa de Cronbach para consistência.

### 2.4 Nível de e-participação alcançado

| Nível (ONU) | Situação |
|---|---|
| e-informação | Atingido: indicadores, mapa, ficha municipal e dados abertos |
| e-consulta | Atingido em protótipo: sugestões e avaliação registradas localmente |
| e-decisão | Não atingido: as sugestões ainda não entram no índice de prioridade nem chegam ao órgão |

## 3. Protocolo e ética

1. Termo de consentimento livre e esclarecido; se houver coleta de dados de pessoas, verificar a necessidade de submissão ao CEP (Plataforma Brasil).
2. Sessão de 30–40 min: apresentação (5), tarefas (15–20), uso livre (5), SUS + questionário (5–10).
3. Registrar tempo e acerto em planilha; gravar tela apenas com consentimento.
4. Não coletar nome nem dado pessoal no formulário de participação durante o teste.

## 4. Limitações conhecidas

- **Dados de demonstração.** A versão publicada usa dados sintéticos; as conclusões só valem após rodar com as exportações reais do SINIR.
- **Granularidade da massa.** Em 2019–2020 a massa só está disponível por UF, o que impede o kg/hab. municipal nesses anos.
- **Contagem de pontos não mede acesso.** Um município pode cumprir a densidade com pontos concentrados em um bairro. A extensão natural é usar coordenadas dos pontos e malha de setores censitários para medir distância de caminhada.
- **Meta de peso.** O percentual de peso do Decreto depende do volume colocado no mercado em 2018, dado que não está no SINIR; o painel mostra a meta, mas não calcula o cumprimento.
- **Participação local.** Contribuições ficam no navegador; produção exige backend, moderação e LGPD.
