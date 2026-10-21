# Métricas da comparação A–E

O runner da campanha chama `tools/runtime_metrics/compute_metrics.py` sobre os
eventos coletados e produz `task-summary.csv`. O script local
[render_event_charts.py](render_event_charts.py) transforma esse CSV em um gráfico
de recuperação. Ambos os artefatos ficam junto da execução em `../benchmarks/results/`.
As medidas dependem do recorte correto dos eventos; veja o
[guia de avaliação](../../../../docs/evaluation.md).
