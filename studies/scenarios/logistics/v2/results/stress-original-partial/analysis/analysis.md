# Logística complexa: desenvolvimento da equipe original

Fonte: `/Users/insider/Desktop/TG/discovery-undergraduate-thesis/studies/scenarios/logistics/v2/results/stress-original-partial/results.json`. Modo: `real-llm`. Modelo: `gpt-5.6-luna`.

15 observações; 8 casos distintos.

Atendimento = entregues / total de pedidos × 100. No prazo = entregues no prazo / total de pedidos × 100, incluindo os não atendidos no denominador. Cada célula mostra a média das observações daquele caso/configuração e seu n válido. Valores ausentes permanecem vazios no CSV e aparecem como “ausente” aqui; zero é um valor medido. Quando total_orders é zero ou ausente, as porcentagens ficam ausentes.

Tokens totais só são calculados quando entrada e saída estão presentes na mesma observação. Tempo real inclui todas as fases medidas pelo coletor, inclusive relatório quando aplicável. Distância e energia baixas devem ser interpretadas junto ao atendimento: uma execução parcial pode consumir menos simplesmente porque deixou pedidos sem entrega.

Não há intervalos de confiança ou testes de significância. Casos diferentes não são tratados como repetições; n=1 é uma observação descritiva. Repetições com falha e resultados parciais permanecem nas tabelas e nas médias quando há métricas medidas. As médias de métricas diferentes podem ter amostras válidas diferentes, indicadas por n. O pareamento das figuras é por caso e configuração dentro do mesmo modo/modelo; as repetições de cada configuração podem ter contagens diferentes. O JSON de entrada precisa representar as mesmas regras e casos para que a comparação seja válida.

## Cobertura das comparações

**Ariadne × Single LLM**: 7 casos pareados.

Casos presentes somente no baseline, excluídos desta comparação: s08-cascading-disruptions.

Casos presentes somente nesta configuração, excluídos desta comparação: nenhum.

## Todas as observações resumidas por caso

| Caso | Configuração | n total | Atendidos (%) | No prazo (%) | Tempo real (s) | Tokens | Distância | Energia | Rejeitadas | Execuções com erro | Resultados |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s01-distributed-mixed-orders | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 79,27 (n=1) | 10.521,00 (n=1) | 90,00 (n=1) | 371,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s01-distributed-mixed-orders | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 34,76 (n=1) | 21.073,00 (n=1) | 59,00 (n=1) | 241,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s02-scarce-stock-coupling | Single LLM | 1 | 75,00 (n=1) | 75,00 (n=1) | 57,37 (n=1) | 17.500,00 (n=1) | 47,00 (n=1) | 210,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| s02-scarce-stock-coupling | Ariadne | 1 | 75,00 (n=1) | 75,00 (n=1) | 93,08 (n=1) | 43.337,00 (n=1) | 53,00 (n=1) | 257,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| s03-capacity-and-source | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 45,07 (n=1) | 7.915,00 (n=1) | 97,00 (n=1) | 374,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s03-capacity-and-source | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 46,70 (n=1) | 22.438,00 (n=1) | 66,00 (n=1) | 261,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s04-recharge-detours | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 28,96 (n=1) | 5.755,00 (n=1) | 38,00 (n=1) | 143,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s04-recharge-detours | Ariadne | 1 | 83,33 (n=1) | 83,33 (n=1) | 211,71 (n=1) | 86.080,00 (n=1) | 43,00 (n=1) | 164,00 (n=1) | 0,00 (n=1) | 0 | {"partial": 1} |
| s05-directed-connections | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 44,78 (n=1) | 11.792,00 (n=1) | 67,00 (n=1) | 273,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s05-directed-connections | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 37,76 (n=1) | 16.845,00 (n=1) | 44,00 (n=1) | 203,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s06-progressive-roadblocks | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 108,44 (n=1) | 26.280,00 (n=1) | 74,00 (n=1) | 285,00 (n=1) | 1,00 (n=1) | 0 | {"complete": 1} |
| s06-progressive-roadblocks | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 333,86 (n=1) | 136.739,00 (n=1) | 81,00 (n=1) | 332,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s07-loaded-vehicle-loss | Single LLM | 1 | 100,00 (n=1) | 100,00 (n=1) | 67,26 (n=1) | 11.853,00 (n=1) | 59,00 (n=1) | 237,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s07-loaded-vehicle-loss | Ariadne | 1 | 100,00 (n=1) | 100,00 (n=1) | 78,46 (n=1) | 28.931,00 (n=1) | 55,00 (n=1) | 222,00 (n=1) | 0,00 (n=1) | 0 | {"complete": 1} |
| s08-cascading-disruptions | Single LLM | 1 | 90,00 (n=1) | 90,00 (n=1) | 191,92 (n=1) | 43.675,00 (n=1) | 71,00 (n=1) | 287,00 (n=1) | 1,00 (n=1) | 0 | {"partial": 1} |

## Arquivos

- [Observações e métricas derivadas](observations.csv).
- [Médias e contagens válidas por caso/configuração](case_summary.csv).
- [single-llm-vs-ariadne-af7d6d42/01-atendimento.svg](single-llm-vs-ariadne-af7d6d42/01-atendimento.svg).
- [single-llm-vs-ariadne-af7d6d42/01-atendimento.png](single-llm-vs-ariadne-af7d6d42/01-atendimento.png).
- [single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.svg](single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.svg).
- [single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.png](single-llm-vs-ariadne-af7d6d42/02-tempo-e-tokens.png).
- [single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.svg](single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.svg).
- [single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.png](single-llm-vs-ariadne-af7d6d42/03-distancia-e-energia.png).
