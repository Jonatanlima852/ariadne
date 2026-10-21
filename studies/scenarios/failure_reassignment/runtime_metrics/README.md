# Métricas de recuperação

Exporte os eventos de uma execução deste cenário, sem misturar outras execuções.
Da raiz do repositório:

```sh
mkdir -p studies/scenarios/failure_reassignment/runtime_metrics/results
python3 tools/runtime_metrics/compute_metrics.py \
  --events .ariadne/runs/ID/events.jsonl \
  --output studies/scenarios/failure_reassignment/runtime_metrics/results/summary.csv
```

Observe `reassignment_count`, `recovery_ms` e `total_latency_ms`. O cálculo usa
atribuição como início da execução; não separa transporte de processamento.
[Definição das métricas](../../../../tools/runtime_metrics/README.md).
