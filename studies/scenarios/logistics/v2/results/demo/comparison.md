Demonstração determinística de integração em Docker, sem benchmark de LLM.

| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | LLM | Tokens entrada/saída | Resultado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| easy | single-llm | 1/1 | 1 | 0 | 0.211 | 2 | 10 | 0 | None/None | complete |
| easy | ariadne | 1/1 | 1 | 0 | 0.512 | 2.0 | 10.0 | 0 | None/None | complete |
| two-orders | single-llm | 2/2 | 2 | 0 | 0.038 | 5 | 33 | 0 | None/None | complete |
| two-orders | ariadne | 2/2 | 2 | 0 | 0.154 | 5.0 | 33.0 | 0 | None/None | complete |
| stock-contention | single-llm | 1/2 | 1 | 0 | 0.020 | 2 | 10 | 0 | None/None | partial |
| stock-contention | ariadne | 1/2 | 1 | 0 | 0.113 | 2.0 | 10.0 | 0 | None/None | partial |
| one-vehicle | single-llm | 2/2 | 2 | 0 | 0.024 | 9 | 55 | 0 | None/None | complete |
| one-vehicle | ariadne | 2/2 | 2 | 0 | 0.140 | 9.0 | 55.0 | 0 | None/None | complete |
| recharge | single-llm | 1/1 | 1 | 0 | 0.023 | 9 | 55 | 0 | None/None | complete |
| recharge | ariadne | 1/1 | 1 | 0 | 0.098 | 9.0 | 55.0 | 0 | None/None | complete |
| priority-deadlines | single-llm | 3/3 | 3 | 0 | 0.056 | 10 | 67 | 0 | None/None | complete |
| priority-deadlines | ariadne | 3/3 | 3 | 0 | 0.225 | 10.0 | 67.0 | 0 | None/None | complete |
| road-block | single-llm | 2/2 | 2 | 0 | 0.033 | 11 | 67 | 0 | None/None | complete |
| road-block | ariadne | 2/2 | 2 | 0 | 0.278 | 11.0 | 67.0 | 0 | None/None | complete |
| vehicle-loss | single-llm | 2/2 | 2 | 0 | 0.030 | 12 | 71 | 0 | None/None | complete |
| vehicle-loss | ariadne | 2/2 | 2 | 0 | 0.185 | 12.0 | 71.0 | 0 | None/None | complete |
| capacity-impossible | single-llm | 1/2 | 1 | 0 | 0.025 | 2 | 10 | 0 | None/None | partial |
| capacity-impossible | ariadne | 1/2 | 1 | 0 | 0.157 | 2.0 | 10.0 | 0 | None/None | partial |
| combined-incidents | single-llm | 3/3 | 3 | 0 | 0.044 | 14 | 89 | 0 | None/None | complete |
| combined-incidents | ariadne | 3/3 | 3 | 0 | 0.295 | 14.0 | 89.0 | 0 | None/None | complete |
