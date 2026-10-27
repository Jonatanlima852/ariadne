LLM real em contêineres Docker independentes; gpt-5.6-luna; uma observação por caso/configuração.

| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | LLM | Tokens entrada/saída | Resultado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| easy | single-llm | 1/1 | 1 | 0 | 3.762 | 2 | 10 | 1 | 1298.0/197.0 | complete |
| easy | ariadne | 1/1 | 1 | 0 | 13.713 | 2.0 | 10.0 | 3 | 3844.0/801.0 | complete |
| two-orders | single-llm | 2/2 | 2 | 0 | 5.994 | 7 | 42 | 1 | 1411.0/486.0 | complete |
| two-orders | ariadne | 2/2 | 2 | 0 | 15.744 | 5.0 | 33.0 | 3 | 5322.0/1191.0 | complete |
| stock-contention | single-llm | 1/2 | 1 | 0 | 6.701 | 2 | 10 | 2 | 3026.0/456.0 | partial |
| stock-contention | ariadne | 1/2 | 1 | 0 | 21.712 | 2.0 | 10.0 | 3 | 4451.0/1687.0 | partial |
| one-vehicle | single-llm | 2/2 | 2 | 0 | 9.653 | 9 | 55 | 1 | 1366.0/891.0 | complete |
| one-vehicle | ariadne | 2/2 | 2 | 0 | 20.166 | 9.0 | 55.0 | 3 | 5339.0/1502.0 | complete |
| recharge | single-llm | 1/1 | 1 | 0 | 6.050 | 9 | 55 | 1 | 1253.0/540.0 | complete |
| recharge | ariadne | 1/1 | 1 | 0 | 14.342 | 9.0 | 55.0 | 3 | 4410.0/975.0 | complete |
| priority-deadlines | single-llm | 3/3 | 3 | 0 | 9.880 | 11 | 70 | 1 | 1523.0/977.0 | complete |
| priority-deadlines | ariadne | 3/3 | 3 | 0 | 20.436 | 10.0 | 67.0 | 3 | 6742.0/1705.0 | complete |
| road-block | single-llm | 2/2 | 2 | 0 | 12.568 | 13 | 76 | 2 | 3053.0/1210.0 | complete |
| road-block | ariadne | 2/2 | 2 | 0 | 35.617 | 11.0 | 67.0 | 5 | 9689.0/2752.0 | complete |
| vehicle-loss | single-llm | 2/2 | 2 | 0 | 11.650 | 12 | 71 | 2 | 2995.0/1101.0 | complete |
| vehicle-loss | ariadne | 2/2 | 2 | 0 | 43.650 | 12.0 | 71.0 | 5 | 9959.0/3383.0 | complete |
| capacity-impossible | single-llm | 1/2 | 1 | 0 | 8.029 | 2 | 10 | 2 | 3025.0/524.0 | partial |
| capacity-impossible | ariadne | 1/2 | 1 | 0 | 17.946 | 2.0 | 10.0 | 3 | 4434.0/1384.0 | partial |
| combined-incidents | single-llm | 3/3 | 3 | 0 | 23.125 | 13 | 74 | 3 | 5073.0/2294.0 | complete |
| combined-incidents | ariadne | 3/3 | 3 | 0 | 64.142 | 14.0 | 89.0 | 7 | 15726.0/4957.0 | complete |
