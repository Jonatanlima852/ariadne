# Logística complexa: Single LLM e Ariadne enxuta

Fonte: `/Users/insider/Desktop/TG/discovery-undergraduate-thesis/studies/scenarios/logistics/v2/results/stress-lean/results.json`. Modo: `real-llm`. Modelo: `gpt-5.6-luna`.

60 observações; 10 casos distintos.

Atendimento = entregues / total de pedidos × 100. No prazo = entregues no prazo / total de pedidos × 100, incluindo os não atendidos no denominador. Cada célula mostra a média das observações daquele caso/configuração e seu n válido. Valores ausentes permanecem vazios no CSV e aparecem como “ausente” aqui; zero é um valor medido. Quando total_orders é zero ou ausente, as porcentagens ficam ausentes.

Tokens totais só são calculados quando entrada e saída estão presentes na mesma observação. Tempo real inclui todas as fases medidas pelo coletor, inclusive relatório quando aplicável. Distância e energia baixas devem ser interpretadas junto ao atendimento: uma execução parcial pode consumir menos simplesmente porque deixou pedidos sem entrega.

Não há intervalos de confiança ou testes de significância. Casos diferentes não são tratados como repetições; n=1 é uma observação descritiva. Repetições com falha e resultados parciais permanecem nas tabelas e nas médias quando há métricas medidas. As médias de métricas diferentes podem ter amostras válidas diferentes, indicadas por n. O pareamento das figuras é por caso e configuração dentro do mesmo modo/modelo; as repetições de cada configuração podem ter contagens diferentes. O JSON de entrada precisa representar as mesmas regras e casos para que a comparação seja válida.

## Cobertura das comparações

**Ariadne enxuta × Single LLM**: 10 casos pareados.

Casos presentes somente no baseline, excluídos desta comparação: nenhum.

Casos presentes somente nesta configuração, excluídos desta comparação: nenhum.

## Todas as observações resumidas por caso

| Caso | Configuração | n total | Atendidos (%) | No prazo (%) | Tempo real (s) | Tokens | Distância | Energia | Rejeitadas | Execuções com erro | Resultados |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s01-distributed-mixed-orders | Single LLM | 3 | 100,00 (n=3) | 91,67 (n=3) | 53,00 (n=3) | 8.042,67 (n=3) | 70,00 (n=3) | 293,67 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s01-distributed-mixed-orders | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 4,82 (n=3) | 1.095,00 (n=3) | 59,00 (n=3) | 241,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s02-scarce-stock-coupling | Single LLM | 3 | 75,00 (n=3) | 70,83 (n=3) | 79,91 (n=3) | 23.554,33 (n=3) | 58,00 (n=3) | 259,33 (n=3) | 0,67 (n=3) | 0 | {"partial": 3} |
| s02-scarce-stock-coupling | Ariadne enxuta | 3 | 75,00 (n=3) | 75,00 (n=3) | 4,90 (n=3) | 1.088,67 (n=3) | 45,00 (n=3) | 213,00 (n=3) | 0,00 (n=3) | 0 | {"partial": 3} |
| s03-capacity-and-source | Single LLM | 3 | 100,00 (n=3) | 100,00 (n=3) | 54,06 (n=3) | 9.680,00 (n=3) | 81,33 (n=3) | 320,33 (n=3) | 0,33 (n=3) | 0 | {"complete": 3} |
| s03-capacity-and-source | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 4,92 (n=3) | 1.099,00 (n=3) | 66,00 (n=3) | 261,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s04-recharge-detours | Single LLM | 3 | 100,00 (n=3) | 94,44 (n=3) | 66,50 (n=3) | 14.162,00 (n=3) | 76,67 (n=3) | 279,33 (n=3) | 0,33 (n=3) | 0 | {"complete": 3} |
| s04-recharge-detours | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 4,27 (n=3) | 933,00 (n=3) | 50,00 (n=3) | 187,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s05-directed-connections | Single LLM | 3 | 100,00 (n=3) | 94,44 (n=3) | 55,23 (n=3) | 10.250,00 (n=3) | 53,00 (n=3) | 223,33 (n=3) | 0,33 (n=3) | 0 | {"complete": 3} |
| s05-directed-connections | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 4,04 (n=3) | 931,33 (n=3) | 44,00 (n=3) | 203,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s06-progressive-roadblocks | Single LLM | 3 | 100,00 (n=3) | 100,00 (n=3) | 139,93 (n=3) | 25.507,33 (n=3) | 79,33 (n=3) | 289,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s06-progressive-roadblocks | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 5,30 (n=3) | 1.062,67 (n=3) | 68,00 (n=3) | 263,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s07-loaded-vehicle-loss | Single LLM | 3 | 88,89 (n=3) | 88,89 (n=3) | 95,71 (n=3) | 22.898,67 (n=3) | 53,00 (n=3) | 224,67 (n=3) | 1,67 (n=3) | 0 | {"complete": 2, "partial": 1} |
| s07-loaded-vehicle-loss | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 4,11 (n=3) | 928,00 (n=3) | 55,00 (n=3) | 222,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s08-cascading-disruptions | Single LLM | 3 | 60,00 (n=3) | 53,33 (n=3) | 198,80 (n=3) | 55.331,00 (n=2) | 76,67 (n=3) | 307,33 (n=3) | 0,67 (n=3) | 1 | {"error": 1, "partial": 1, "complete": 1} |
| s08-cascading-disruptions | Ariadne enxuta | 3 | 100,00 (n=3) | 100,00 (n=3) | 6,04 (n=3) | 1.190,33 (n=3) | 108,00 (n=3) | 440,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s09-deadline-and-priority-pressure | Single LLM | 3 | 100,00 (n=3) | 70,83 (n=3) | 71,34 (n=3) | 12.156,67 (n=3) | 56,00 (n=3) | 215,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s09-deadline-and-priority-pressure | Ariadne enxuta | 3 | 100,00 (n=3) | 62,50 (n=3) | 5,89 (n=3) | 1.045,33 (n=3) | 62,00 (n=3) | 245,00 (n=3) | 0,00 (n=3) | 0 | {"complete": 3} |
| s10-infeasible-among-feasible | Single LLM | 3 | 83,33 (n=3) | 83,33 (n=3) | 56,34 (n=3) | 14.683,00 (n=3) | 52,33 (n=3) | 208,00 (n=3) | 0,33 (n=3) | 0 | {"partial": 3} |
| s10-infeasible-among-feasible | Ariadne enxuta | 3 | 87,50 (n=3) | 87,50 (n=3) | 4,53 (n=3) | 1.064,33 (n=3) | 53,00 (n=3) | 223,00 (n=3) | 0,00 (n=3) | 0 | {"partial": 3} |

## Erros registrados

- Observação 15, s08-cascading-disruptions / single-llm: AssertionError: task 5ba95be4-f7d0-4ff5-b5e9-952ff40cc7bc did not complete: OpenAI call failed (APITimeoutError)

## Arquivos

- [Observações e métricas derivadas](observations.csv).
- [Médias e contagens válidas por caso/configuração](case_summary.csv).
- [single-llm-vs-ariadne-lean-7dfe317c/01-atendimento.svg](single-llm-vs-ariadne-lean-7dfe317c/01-atendimento.svg).
- [single-llm-vs-ariadne-lean-7dfe317c/01-atendimento.png](single-llm-vs-ariadne-lean-7dfe317c/01-atendimento.png).
- [single-llm-vs-ariadne-lean-7dfe317c/02-tempo-e-tokens.svg](single-llm-vs-ariadne-lean-7dfe317c/02-tempo-e-tokens.svg).
- [single-llm-vs-ariadne-lean-7dfe317c/02-tempo-e-tokens.png](single-llm-vs-ariadne-lean-7dfe317c/02-tempo-e-tokens.png).
- [single-llm-vs-ariadne-lean-7dfe317c/03-distancia-e-energia.svg](single-llm-vs-ariadne-lean-7dfe317c/03-distancia-e-energia.svg).
- [single-llm-vs-ariadne-lean-7dfe317c/03-distancia-e-energia.png](single-llm-vs-ariadne-lean-7dfe317c/03-distancia-e-energia.png).
