# Benchmark: failure_reassignment

Da raiz: `sh studies/scenarios/failure_reassignment/benchmarks/run.sh`.

A topologia está em [compose.yaml](compose.yaml) e os casos em [run.py](run.py).
O runner inicia o runtime e os agentes, executa a medição e exporta JSON, CSV,
gráfico de latência, eventos e métricas para `results/<data-UTC>/`.
Não requer chave de LLM ou arquivo .env.

Os rótulos A–D foram mantidos nos dados para facilitar comparação histórica.
Rotas (C) e recuperação (D) usam uma amostra; são verificações de integração,
não estimativas estatísticas. A carga dos agentes na seleção é configurada.
