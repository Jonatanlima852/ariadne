# Logística v3: comparação por caso

Fonte: `/Users/insider/Desktop/TG/discovery-undergraduate-thesis/studies/scenarios/logistics/v3/results/2026-10-30/basic/analysis/results.json`. Modo: `real-llm`. Modelo: `gpt-5.6-luna`.

20 observações; 10 casos distintos.

Atendimento = entregues / total de pedidos × 100. No prazo = entregues no prazo / total de pedidos × 100, incluindo os não atendidos no denominador. Cada célula mostra a média das observações daquele caso/configuração e seu n válido. Valores ausentes permanecem vazios no CSV e aparecem como “ausente” aqui; zero é um valor medido. Quando total_orders é zero ou ausente, as porcentagens ficam ausentes.

Tokens totais só são calculados quando entrada e saída estão presentes na mesma observação. Tempo real inclui todas as fases medidas pelo coletor, inclusive relatório quando aplicável. Distância e energia baixas devem ser interpretadas junto ao atendimento: uma execução parcial pode consumir menos simplesmente porque deixou pedidos sem entrega.

Não há intervalos de confiança ou testes de significância. Casos diferentes não são tratados como repetições; n=1 é uma observação descritiva. Repetições com falha e resultados parciais permanecem nas tabelas e nas médias quando há métricas medidas. As médias de métricas diferentes podem ter amostras válidas diferentes, indicadas por n. O pareamento das figuras é por caso e configuração dentro do mesmo modo/modelo; as repetições de cada configuração podem ter contagens diferentes. O JSON de entrada precisa representar as mesmas regras e casos para que a comparação seja válida.

## Cobertura das comparações

**Ariadne v3 (planejador + BDI) × Single LLM**: 10 casos pareados.

Casos presentes somente no baseline, excluídos desta comparação: nenhum.

Casos presentes somente nesta configuração, excluídos desta comparação: nenhum.

## Todas as observações resumidas por caso

| Caso | Configuração | n total | Atendidos (%) | No prazo (%) | Tempo real (s) | Tokens | Distância | Energia | Rejeitadas | Execuções com erro | Resultados |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| combined-incidents | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 35,99 (n=1) | 11.677,00 (n=1) | 19,00 (n=1) | 116,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| combined-incidents | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 31,06 (n=1) | 7.195,00 (n=1) | 13,00 (n=1) | 74,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| capacity-impossible | Ariadne v3 (planejador + BDI) | 1 | 50,00 (n=1) | 50,00 (n=1) | 13,59 (n=1) | 4.148,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| capacity-impossible | Single LLM (missão) | 1 | 50,00 (n=1) | 50,00 (n=1) | 10,31 (n=1) | 3.438,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| stock-contention | Single LLM (missão) | 1 | 50,00 (n=1) | 50,00 (n=1) | 7,28 (n=1) | 3.173,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| recharge | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 4,34 (n=1) | 1.726,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| road-block | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 21,77 (n=1) | 4.614,00 (n=1) | 15,00 (n=1) | 91,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| stock-contention | Ariadne v3 (planejador + BDI) | 1 | 50,00 (n=1) | 50,00 (n=1) | 8,89 (n=1) | 3.762,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| two-orders | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 5,44 (n=1) | 1.701,00 (n=1) | 5,00 (n=1) | 33,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| road-block | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 11,10 (n=1) | 4.167,00 (n=1) | 16,00 (n=1) | 98,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| vehicle-loss | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 13,43 (n=1) | 5.950,00 (n=1) | 12,00 (n=1) | 71,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| one-vehicle | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 8,70 (n=1) | 3.679,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| priority-deadlines | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 8,33 (n=1) | 2.097,00 (n=1) | 6,00 (n=1) | 37,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| priority-deadlines | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 11,07 (n=1) | 4.219,00 (n=1) | 10,00 (n=1) | 67,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| recharge | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 6,34 (n=1) | 1.640,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| easy | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 4,97 (n=1) | 1.736,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| easy | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 4,16 (n=1) | 1.386,00 (n=1) | 2,00 (n=1) | 10,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| two-orders | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 4,80 (n=1) | 1.884,00 (n=1) | 5,00 (n=1) | 33,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| vehicle-loss | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 18,57 (n=1) | 4.248,00 (n=1) | 12,00 (n=1) | 71,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| one-vehicle | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 6,77 (n=1) | 1.786,00 (n=1) | 9,00 (n=1) | 55,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |

## Arquivos

- [Observações e métricas derivadas](observations.csv).
- [Médias e contagens válidas por caso/configuração](case_summary.csv).

Nenhuma figura exportada. A opção --no-plots solicita somente tabelas.
