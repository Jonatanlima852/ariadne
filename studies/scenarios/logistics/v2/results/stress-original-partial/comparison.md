stress · real-llm · Docker · 1 observação(ões) por caso/configuração.

**Coleta incompleta:** 15/20 observações. Não compare totais de grupos com cobertura diferente.

| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | LLM | Tokens entrada/saída | Resultado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s01-distributed-mixed-orders | single-llm | 8/8 | 8 | 0 | 79.270 | 90 | 371 | 1 | 3102.0/7419.0 | complete |
| s01-distributed-mixed-orders | ariadne | 8/8 | 8 | 0 | 34.764 | 59.0 | 241.0 | 3 | 17889.0/3184.0 | complete |
| s02-scarce-stock-coupling | single-llm | 6/8 | 6 | 0 | 57.372 | 47 | 210 | 3 | 12186.0/5314.0 | partial |
| s02-scarce-stock-coupling | ariadne | 6/8 | 6 | 0 | 93.082 | 53.0 | 257.0 | 7 | 35909.0/7428.0 | partial |
| s03-capacity-and-source | single-llm | 8/8 | 8 | 0 | 45.075 | 97 | 374 | 1 | 3122.0/4793.0 | complete |
| s03-capacity-and-source | ariadne | 8/8 | 8 | 0 | 46.702 | 66.0 | 261.0 | 3 | 18328.0/4110.0 | complete |
| s04-recharge-detours | single-llm | 6/6 | 6 | 0 | 28.964 | 38 | 143 | 1 | 2828.0/2927.0 | complete |
| s04-recharge-detours | ariadne | 5/6 | 5 | 0 | 211.713 | 43.0 | 164.0 | 15 | 69869.0/16211.0 | partial |
| s05-directed-connections | single-llm | 6/6 | 6 | 1 | 44.784 | 67 | 273 | 2 | 7315.0/4477.0 | complete |
| s05-directed-connections | ariadne | 6/6 | 6 | 0 | 37.759 | 44.0 | 203.0 | 3 | 13642.0/3203.0 | complete |
| s06-progressive-roadblocks | single-llm | 8/8 | 8 | 1 | 108.442 | 74 | 285 | 4 | 15916.0/10364.0 | complete |
| s06-progressive-roadblocks | ariadne | 8/8 | 8 | 0 | 333.861 | 81.0 | 332.0 | 21 | 111096.0/25643.0 | complete |
| s07-loaded-vehicle-loss | single-llm | 6/6 | 6 | 0 | 67.264 | 59 | 237 | 2 | 5837.0/6016.0 | complete |
| s07-loaded-vehicle-loss | ariadne | 6/6 | 6 | 0 | 78.459 | 55.0 | 222.0 | 5 | 22183.0/6748.0 | complete |
| s08-cascading-disruptions | single-llm | 9/10 | 9 | 1 | 191.921 | 71 | 287 | 6 | 26155.0/17520.0 | partial |
