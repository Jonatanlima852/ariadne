# Extração de métricas

[compute_metrics.py](compute_metrics.py) lê eventos do Orchestrator e produz
um CSV por tarefa, com latência de atribuição, execução, total, recuperação e
contagem de reassignment. Usa apenas a biblioteca padrão do Python.

Da raiz, com o JSONL previamente exportado e isolado para a execução desejada:

```sh
python3 studies/runtime_metrics/compute_metrics.py \
  --events studies/runtime_metrics/results/events.jsonl \
  --output studies/runtime_metrics/results/summary.csv
```

O cálculo atual usa `TASK_ASSIGNED` como início da latência de execução; não
separa o tempo de transporte do processamento interno do agente. O script
reconhece também eventos terminais de workflow. Não misture eventos do broker,
que podem não ter `task_id`, com essa entrada.

[Avaliação e limites das métricas](../../docs/evaluation.md)
