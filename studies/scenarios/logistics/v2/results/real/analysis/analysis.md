# Logística básica: configuração original

Fonte: `/Users/insider/Desktop/TG/discovery-undergraduate-thesis/studies/scenarios/logistics/v2/results/real/results.json`. Modo: `real-llm`. Modelo: `gpt-5.6-luna`.

20 observações; 10 casos distintos.

Atendimento = entregues / total de pedidos × 100. No prazo = entregues no prazo / total de pedidos × 100, incluindo os não atendidos no denominador. Cada célula mostra a média das observações daquele caso/configuração e seu n válido. Valores ausentes permanecem vazios no CSV e aparecem como “ausente” aqui; zero é um valor medido. Quando total_orders é zero ou ausente, as porcentagens ficam ausentes.

Tokens totais só são calculados quando entrada e saída estão presentes na mesma observação. Tempo real inclui todas as fases medidas pelo coletor, inclusive relatório quando aplicável. Distância e energia baixas devem ser interpretadas junto ao atendimento: uma execução parcial pode consumir menos simplesmente porque deixou pedidos sem entrega.

Não há intervalos de confiança ou testes de significância. Casos diferentes não são tratados como repetições; n=1 é uma observação descritiva. Repetições com falha e resultados parciais permanecem nas tabelas e nas médias quando há métricas medidas. As médias de métricas diferentes podem ter amostras válidas diferentes, indicadas por n. O pareamento das figuras é por caso e configuração dentro do mesmo modo/modelo; as repetições de cada configuração podem ter contagens diferentes. O JSON de entrada precisa representar as mesmas regras e casos para que a comparação seja válida.

## Cobertura das comparações

**Ariadne × Single LLM**: 10 casos pareados.

Casos presentes somente no baseline, excluídos desta comparação: nenhum.

Casos presentes somente nesta configuração, excluídos desta comparação: nenhum.

## Todas as observações resumidas por caso

| Caso | Configuração | n total | Atendidos (%) | No prazo (%) | Tempo real (s) | Tokens | Distância | Energia | Rejeitadas | Execuções com erro | Resultados |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| easy | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 3,76 (n=1) | 1.495,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| easy | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 13,71 (n=1) | 4.645,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| two-orders | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 5,99 (n=1) | 1.897,00 (n=1) | 7,00 (n=1) | 42,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| two-orders | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 15,74 (n=1) | 6.513,00 (n=1) | 5,00 (n=1) | 33,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| stock-contention | Single LLM | 1 | 50,00 (n=1) | 50,00 (n=1) | 6,70 (n=1) | 3.482,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| stock-contention | Ariadne | 1 | 50,00 (n=1) | 50,00 (n=1) | 21,71 (n=1) | 6.138,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| one-vehicle | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 9,65 (n=1) | 2.257,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| one-vehicle | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 20,17 (n=1) | 6.841,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| recharge | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 6,05 (n=1) | 1.793,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| recharge | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 14,34 (n=1) | 5.385,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| priority-deadlines | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 9,88 (n=1) | 2.500,00 (n=1) | 11,00 (n=1) | 70,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| priority-deadlines | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 20,44 (n=1) | 8.447,00 (n=1) | 10,00 (n=1) | 67,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| road-block | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 12,57 (n=1) | 4.263,00 (n=1) | 13,00 (n=1) | 76,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| road-block | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 35,62 (n=1) | 12.441,00 (n=1) | 11,00 (n=1) | 67,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| vehicle-loss | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 11,65 (n=1) | 4.096,00 (n=1) | 12,00 (n=1) | 71,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| vehicle-loss | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 43,65 (n=1) | 13.342,00 (n=1) | 12,00 (n=1) | 71,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| capacity-impossible | Single LLM | 1 | 50,00 (n=1) | 50,00 (n=1) | 8,03 (n=1) | 3.549,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| capacity-impossible | Ariadne | 1 | 50,00 (n=1) | 50,00 (n=1) | 17,95 (n=1) | 5.818,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| combined-incidents | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 23,12 (n=1) | 7.367,00 (n=1) | 13,00 (n=1) | 74,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| combined-incidents | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 64,14 (n=1) | 20.683,00 (n=1) | 14,00 (n=1) | 89,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |

## Arquivos

- [Observações e métricas derivadas](observations.csv).
- [Médias e contagens válidas por caso/configuração](case_summary.csv).
- [single-llm-vs-ariadne-af7d6d42/01-atendimento.svg](single-llm-vs-ariadne-af7d6d42/01-atendimento.svg).
- [single-llm-vs-ariadne-af7d6d42/01-atendimento.png](single-llm-vs-ariadne-af7d6d42/01-atendimento.png).
- [single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.svg](single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.svg).
- [single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.png](single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.png).
- [single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.svg](single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.svg).
- [single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.png](single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.png).
