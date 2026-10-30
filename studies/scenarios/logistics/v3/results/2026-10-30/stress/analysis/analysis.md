# Logística v3: comparação por caso

Fonte: `/Users/insider/Desktop/TG/discovery-undergraduate-thesis/studies/scenarios/logistics/v3/results/2026-10-30/stress/analysis/results.json`. Modo: `real-llm`. Modelo: `gpt-5.6-luna`.

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
| s07-loaded-vehicle-loss | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 58,94 (n=1) | 13.675,00 (n=1) | 50,00 (n=1) | 211,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s01-distributed-mixed-orders | Single LLM (missão) | 1 | 0,00 (n=1) | 0,00 (n=1) | 90,46 (n=1) | ausente (n=0) | 0,00 (n=1) | 0,00 (n=1) | 0,00 (n=1) | 1 | {"partial": 1} |
| s04-recharge-detours | Single LLM (missão) | 1 | 83,33 (n=1) | 83,33 (n=1) | 120,63 (n=1) | 23.689,00 (n=1) | 68,00 (n=1) | 283,00 (n=1) | 2,00 (n=1) | 0 | {"partial": 1} |
| s03-capacity-and-source | Single LLM (missão) | 1 | 100,00 (n=1) | 87,50 (n=1) | 69,63 (n=1) | 8.776,00 (n=1) | 112,00 (n=1) | 468,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s08-cascading-disruptions | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 60,00 (n=1) | 176,66 (n=1) | 46.089,00 (n=1) | 159,00 (n=1) | 704,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s10-infeasible-among-feasible | Single LLM (missão) | 1 | 87,50 (n=1) | 87,50 (n=1) | 51,83 (n=1) | 10.963,00 (n=1) | 47,00 (n=1) | 199,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| s02-scarce-stock-coupling | Single LLM (missão) | 1 | 62,50 (n=1) | 37,50 (n=1) | 266,85 (n=1) | 51.787,00 (n=1) | 109,00 (n=1) | 452,00 (n=1) | 4,00 (n=1) | 0 | {"partial": 1} |
| s09-deadline-and-priority-pressure | Single LLM (missão) | 1 | 100,00 (n=1) | 62,50 (n=1) | 177,34 (n=1) | 21.664,00 (n=1) | 64,00 (n=1) | 241,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s02-scarce-stock-coupling | Ariadne v3 (planejador + BDI) | 1 | 75,00 (n=1) | 62,50 (n=1) | 73,98 (n=1) | 18.111,00 (n=1) | 65,00 (n=1) | 336,00 (n=1) | 2,00 (n=1) | 0 | {"partial": 1} |
| s09-deadline-and-priority-pressure | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 37,50 (n=1) | 73,05 (n=1) | 14.248,00 (n=1) | 78,00 (n=1) | 356,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s06-progressive-roadblocks | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 80,78 (n=1) | 21.486,00 (n=1) | 111,00 (n=1) | 481,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s08-cascading-disruptions | Single LLM (missão) | 1 | 100,00 (n=1) | 70,00 (n=1) | 277,16 (n=1) | 55.874,00 (n=1) | 155,00 (n=1) | 577,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s10-infeasible-among-feasible | Ariadne v3 (planejador + BDI) | 1 | 87,50 (n=1) | 87,50 (n=1) | 74,93 (n=1) | 20.700,00 (n=1) | 83,00 (n=1) | 396,00 (n=1) | 2,00 (n=1) | 0 | {"partial": 1} |
| s06-progressive-roadblocks | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 97,75 (n=1) | 16.760,00 (n=1) | 64,00 (n=1) | 273,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s05-directed-connections | Single LLM (missão) | 1 | 100,00 (n=1) | 100,00 (n=1) | 41,60 (n=1) | 6.255,00 (n=1) | 81,00 (n=1) | 356,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s04-recharge-detours | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 32,96 (n=1) | 7.936,00 (n=1) | 79,00 (n=1) | 352,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s07-loaded-vehicle-loss | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 50,49 (n=1) | 14.841,00 (n=1) | 65,00 (n=1) | 310,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s05-directed-connections | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 34,87 (n=1) | 10.998,00 (n=1) | 64,00 (n=1) | 319,00 (n=1) | 2,00 (n=1) | 0 | {"complete": 1} |
| s01-distributed-mixed-orders | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 50,03 (n=1) | 16.224,00 (n=1) | 74,00 (n=1) | 343,00 (n=1) | 2,00 (n=1) | 0 | {"complete": 1} |
| s03-capacity-and-source | Ariadne v3 (planejador + BDI) | 1 | 100,00 (n=1) | 100,00 (n=1) | 48,51 (n=1) | 12.739,00 (n=1) | 90,00 (n=1) | 394,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |

## Erros registrados

- Observação 2, s01-distributed-mixed-orders / single-llm-v3: no alternative compatible agent found

## Arquivos

- [Observações e métricas derivadas](observations.csv).
- [Médias e contagens válidas por caso/configuração](case_summary.csv).

Nenhuma figura exportada. A opção --no-plots solicita somente tabelas.
