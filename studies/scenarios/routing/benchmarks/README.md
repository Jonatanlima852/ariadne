# Benchmark: routing

Da raiz: `sh studies/scenarios/routing/benchmarks/run.sh`.

A topologia está em [compose.yaml](compose.yaml) e os casos em [run.py](run.py).
O runner inicia o runtime e os agentes, executa a medição e exporta JSON, CSV,
gráfico de latência, eventos e métricas para `results/<data-UTC>/`.
Requer OPENAI_API_KEY no ambiente ou no arquivo BENCHMARK_ENV_FILE (padrão .env).

Os rótulos A–D foram mantidos nos dados para facilitar comparação histórica.
Rotas (C) e recuperação (D) usam uma amostra; são verificações de integração,
não estimativas estatísticas. A carga dos agentes na seleção é configurada.
