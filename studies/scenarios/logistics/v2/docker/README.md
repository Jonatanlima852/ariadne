# Execução em contêineres

Da raiz do repositório:

```sh
LOGISTICS_V2_DEMO=0 docker compose --env-file .env \
  -f studies/scenarios/logistics/v2/docker/compose.yaml up --build --wait -d
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run --cases easy
```

O [Compose](compose.yaml) contém um serviço para cada um dos dez especialistas:
`order-interpreter`, `mission-decomposer`, `incident-analyst`,
`operations-reporter`, `inventory-manager`, `resource-allocator`, `route-planner`,
`energy-manager`, `constraint-supervisor` e `mission-executor`.
A configuração de referência usa o serviço separado `single-llm`.
O serviço adicional `mission-coordinator` é BDI e participa da configuração
`ariadne-lean`, com um LLM e sete BDI. Os serviços da equipe original continuam
disponíveis. Para reproduzir a confirmação enxuta:

```sh
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run \
  --suite stress --repeat 3 --configurations single-llm ariadne-lean
```

Cada serviço constrói seu próprio `agents/<nome>/Dockerfile` e executa somente
`agents.<nome>.main`. Não há um processo Python que hospede vários agentes.

Registry e Orchestrator também são contêineres, usando os Dockerfiles existentes.
O cliente Python roda no host e acessa portas locais 55051/55052. Os agentes
anunciam seus nomes DNS internos ao Registry e recebem tarefas do Orchestrator.
Os BDI instalam somente o SDK básico; os LLM instalam o extra `llm` com as
versões declaradas no SDK.

Sem credenciais, use `LOGISTICS_V2_DEMO=1` no comando de subida e `--demo` no
cliente. Esse modo continua usando os contêineres independentes e o runtime
Go real, com substitutos determinísticos apenas nas chamadas de modelo.
O modo real exige `OPENAI_API_KEY` nos contêineres LLM. Configure `LLM_MODEL`
igualmente para os cinco serviços LLM. Recrie os serviços ao trocar modo/modelo.

```sh
# Conferir os serviços e seus estados:
docker compose -f studies/scenarios/logistics/v2/docker/compose.yaml ps

# Consultar os logs de um especialista:
docker compose -f studies/scenarios/logistics/v2/docker/compose.yaml logs mission-executor

# Exportar eventos do runtime, se necessário:
docker compose -f studies/scenarios/logistics/v2/docker/compose.yaml \
  exec -T orchestrator cat /data/events.jsonl > /tmp/logistics-v2-events.jsonl

# Encerrar este cenário, preservando o volume de eventos:
docker compose -f studies/scenarios/logistics/v2/docker/compose.yaml down
```

O runner não sobe nem encerra contêineres. Ele descobre as capacidades no Registry,
confere o modo real/demonstração e envia tarefas/workflows. Os resultados ficam
em `.ariadne/logistics-v2/<id>/`, com estado e métricas por caso/configuração.
