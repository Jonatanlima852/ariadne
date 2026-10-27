Suíte stress · deterministic-integration-demo · Docker · uma observação por caso/configuração.

| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | LLM | Tokens entrada/saída | Resultado |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s01-distributed-mixed-orders | single-llm | 8/8 | 8 | 0 | 0.445 | 59 | 241 | 0 | None/None | complete |
| s01-distributed-mixed-orders | ariadne | 8/8 | 8 | 0 | 1.089 | 59.0 | 241.0 | 0 | None/None | complete |
| s02-scarce-stock-coupling | single-llm | 6/8 | 6 | 0 | 0.452 | 53 | 257 | 0 | None/None | partial |
| s02-scarce-stock-coupling | ariadne | 6/8 | 6 | 0 | 1.009 | 53.0 | 257.0 | 0 | None/None | partial |
| s03-capacity-and-source | single-llm | 8/8 | 8 | 0 | 0.415 | 66 | 261 | 0 | None/None | complete |
| s03-capacity-and-source | ariadne | 8/8 | 8 | 0 | 0.868 | 66.0 | 261.0 | 0 | None/None | complete |
| s04-recharge-detours | single-llm | 5/6 | 5 | 0 | 0.224 | 43 | 164 | 0 | None/None | partial |
| s04-recharge-detours | ariadne | 5/6 | 5 | 0 | 1.098 | 43.0 | 164.0 | 0 | None/None | partial |
| s05-directed-connections | single-llm | 6/6 | 6 | 0 | 0.231 | 44 | 203 | 0 | None/None | complete |
| s05-directed-connections | ariadne | 6/6 | 6 | 0 | 0.606 | 44.0 | 203.0 | 0 | None/None | complete |
| s06-progressive-roadblocks | single-llm | 8/8 | 8 | 0 | 0.675 | 81 | 332 | 0 | None/None | complete |
| s06-progressive-roadblocks | ariadne | 8/8 | 8 | 0 | 2.056 | 81.0 | 332.0 | 0 | None/None | complete |
| s07-loaded-vehicle-loss | single-llm | 6/6 | 6 | 0 | 0.217 | 55 | 222 | 0 | None/None | complete |
| s07-loaded-vehicle-loss | ariadne | 6/6 | 6 | 0 | 0.687 | 55.0 | 222.0 | 0 | None/None | complete |
| s08-cascading-disruptions | single-llm | 6/10 | 6 | 0 | 1.011 | 82 | 370 | 0 | None/None | partial |
| s08-cascading-disruptions | ariadne | 6/10 | 6 | 0 | 2.387 | 82.0 | 370.0 | 0 | None/None | partial |
| s09-deadline-and-priority-pressure | single-llm | 8/8 | 5 | 0 | 0.352 | 62 | 245 | 0 | None/None | complete |
| s09-deadline-and-priority-pressure | ariadne | 8/8 | 5 | 0 | 0.840 | 62.0 | 245.0 | 0 | None/None | complete |
| s10-infeasible-among-feasible | single-llm | 7/8 | 7 | 0 | 0.366 | 53 | 223 | 0 | None/None | partial |
| s10-infeasible-among-feasible | ariadne | 7/8 | 7 | 0 | 0.901 | 53.0 | 223.0 | 0 | None/None | partial |
