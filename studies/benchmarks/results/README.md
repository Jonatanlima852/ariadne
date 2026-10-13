# Resultados dos benchmarks

`./benchmarks/run.sh` cria uma pasta datada contendo:

- `events.jsonl`: eventos brutos do Orchestrator;
- `results.json`: resultados e medições do cliente para A-E;
- `summary.csv`: uma linha agregada por cenário/caso;
- `task-summary.csv`: métricas derivadas dos eventos por task;
- `latency.svg`: comparação visual das latências médias;
- `agent-distribution.svg`: distribuição por política e agente;
- `recovery.svg`: tempo de recuperação e latência total com falha;
- `message-count.svg`: indicação de zero envelopes nos workflows avaliados,
  que usam chamadas diretas a AgentService; o broker existe em outro cenário.

As execuções são ignoradas pelo Git para evitar misturar resultados locais e
credenciais indiretas com o código. Resultados escolhidos para a monografia
devem ser copiados conscientemente para o artefato de avaliação.

O experimento de missão logística usa `./benchmarks/run-logistics.sh` e produz
`logistics-results.json`, `logistics-summary.csv`, `logistics-quality.svg` e
`events.jsonl`. A execução selecionada `logistics-20261004T-final-v2` foi
versionada deliberadamente como evidência da avaliação descrita em
[guia público de avaliação](../../docs/evaluation.md).
