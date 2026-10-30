Execução: real-llm. Modelo: gpt-5.6-luna. Laço de missão no orquestrador Go. Gerado em 2026-10-30T06:51:00.136573+00:00.

| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | Rodadas | LLM | Tokens entrada/saída | Ciclos BDI | Paralelo máx. | Reatrib. | Resultado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| combined-incidents | ariadne-v3 | 3/3 | 3 | 0 | 35.987 | 19 | 116 | 6 | 5 | 9053/2624 | 55 | 2 | 0 | complete |
| combined-incidents | single-llm-v3 | 3/3 | 3 | 0 | 31.061 | 13 | 74 | 4 | 3 | 4685/2510 | 0 | 0 | 0 | complete |
| capacity-impossible | ariadne-v3 | 1/2 | 1 | 0 | 13.590 | 2 | 10 | 3 | 2 | 3233/915 | 10 | 1 | 0 | partial |
| capacity-impossible | single-llm-v3 | 1/2 | 1 | 0 | 10.310 | 2 | 10 | 2 | 2 | 2781/657 | 0 | 0 | 0 | partial |
| stock-contention | single-llm-v3 | 1/2 | 1 | 0 | 7.284 | 2 | 10 | 2 | 2 | 2782/391 | 0 | 0 | 0 | partial |
| recharge | ariadne-v3 | 1/1 | 1 | 0 | 4.344 | 9 | 55 | 2 | 1 | 1451/275 | 4 | 1 | 0 | complete |
| road-block | single-llm-v3 | 2/2 | 2 | 0 | 21.772 | 15 | 91 | 3 | 2 | 2811/1803 | 0 | 0 | 0 | complete |
| stock-contention | ariadne-v3 | 1/2 | 1 | 0 | 8.892 | 2 | 10 | 3 | 2 | 3236/526 | 10 | 1 | 0 | partial |
| two-orders | single-llm-v3 | 2/2 | 2 | 0 | 5.440 | 5 | 33 | 2 | 1 | 1296/405 | 0 | 0 | 0 | complete |
| road-block | ariadne-v3 | 2/2 | 2 | 0 | 11.098 | 16 | 98 | 3 | 2 | 3292/875 | 28 | 2 | 0 | complete |
| vehicle-loss | ariadne-v3 | 2/2 | 2 | 0 | 13.431 | 12 | 71 | 4 | 3 | 4987/963 | 36 | 2 | 0 | complete |
| one-vehicle | ariadne-v3 | 2/2 | 2 | 0 | 8.703 | 9 | 55 | 3 | 2 | 3158/521 | 18 | 1 | 0 | complete |
| priority-deadlines | single-llm-v3 | 3/3 | 3 | 0 | 8.331 | 6 | 37 | 2 | 1 | 1405/692 | 0 | 0 | 0 | complete |
| priority-deadlines | ariadne-v3 | 3/3 | 3 | 0 | 11.069 | 10 | 67 | 3 | 2 | 3417/802 | 27 | 2 | 0 | complete |
| recharge | single-llm-v3 | 1/1 | 1 | 0 | 6.341 | 9 | 55 | 2 | 1 | 1151/489 | 0 | 0 | 0 | complete |
| easy | ariadne-v3 | 1/1 | 1 | 0 | 4.974 | 2 | 10 | 2 | 1 | 1491/245 | 9 | 1 | 0 | complete |
| easy | single-llm-v3 | 1/1 | 1 | 0 | 4.155 | 2 | 10 | 2 | 1 | 1188/198 | 0 | 0 | 0 | complete |
| two-orders | ariadne-v3 | 2/2 | 2 | 0 | 4.796 | 5 | 33 | 2 | 1 | 1575/309 | 18 | 2 | 0 | complete |
| vehicle-loss | single-llm-v3 | 2/2 | 2 | 0 | 18.572 | 12 | 71 | 3 | 2 | 2757/1491 | 0 | 0 | 0 | complete |
| one-vehicle | single-llm-v3 | 2/2 | 2 | 0 | 6.766 | 9 | 55 | 2 | 1 | 1257/529 | 0 | 0 | 0 | complete |
