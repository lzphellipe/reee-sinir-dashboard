# Limitações e trabalhos futuros

Corresponde aos dois últimos parágrafos da conclusão do TCC. O objetivo específico IV (avaliação com usuários) foi retirado do trabalho por falta de tempo hábil; por isso o painel não tem mais questionário de avaliação.

## Limitações

| Limitação | Efeito no painel | Onde o painel avisa |
|---|---|---|
| O módulo Estados e Municípios do SINIR não tem campos numéricos de REEE | Pontos e massa vêm dos relatórios das entidades gestoras, agregados por UF | Faixa "Relatórios das entidades" no topo; selos de fonte |
| Relatórios de 2024 e 2025 não publicados no SINIR até 08/10/2026 | 2024 usa os totais nacionais da ABINEE; 2025 só tem dados dos planos municipais | Indicadores marcados "Último dado: …" |
| ABREE 2023 remete os números a um anexo não publicado | 2023 tem só a Green Eletron | Selo de fonte do indicador |
| Só a Green Eletron publica pontos por município (2022) | "PEV listado" e o déficit do simulador são estimativas máximas | Nota do ranking de prioridade |
| Pesos do índice definidos pelo grupo, sem análise de sensibilidade nem validação com gestores | A ordem do ranking não equivale à prioridade real | Nota do ranking de prioridade |
| Cobertura nominal compara só quantidades | Cumprir o número não garante boa distribuição; entidades diferentes podem contar o mesmo local | Dicionário de indicadores |
| Corte de 80 mil habitantes aproxima a lista do Anexo III do Decreto | Pode incluir ou excluir municípios da lista oficial | Subtítulo do ranking ("aproximação") |
| Planos são autodeclarados e em texto livre | Citar REEE não prova execução; não citar não prova ausência | Ficha da cidade mostra o trecho original |
| O efeito sobre o controle social depende de letramento em dados e de canais de resposta do poder público | Não medido neste trabalho | – |

## Trabalhos futuros

1. **Análise de sensibilidade do índice:** variar cada peso de `PESOS_PRIORIDADE_SINIR` e medir quanto o ranking muda (por exemplo, a correlação de Spearman entre os rankings e quantos municípios trocam de classe).
2. **Validação dos pesos com gestores municipais e especialistas.**
3. **Endereços dos pontos de recebimento,** pedidos ao MMA pela Lei de Acesso à Informação (modelos em [`05_pedido_lai.md`](05_pedido_lai.md)), para calcular o déficit por município e a distribuição no território.
4. **Atualização da base** à medida que os relatórios de 2024 e 2025 forem publicados no SINIR, que costuma publicá-los com atraso.
5. **Avaliação com usuários** (teste de tarefas com servidores municipais e escala de usabilidade), retirada do escopo deste TCC.
