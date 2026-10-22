# Métricas da rota heterogênea

O cliente salva seu relatório em `results/heterogeneous-report.json` quando não
há `SCENARIO_REPORT_PATH`. Pelo launcher, as evidências ficam em `.ariadne/runs/`.
Para analisar eventos, use o [extrator compartilhado](../../../../tools/runtime_metrics/README.md)
e salve a saída em `runtime_metrics/results/` deste cenário. Distingua duração
do workflow, duração das etapas e tempo das chamadas ao provedor.
