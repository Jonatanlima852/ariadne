# Execução em contêineres (v3)

Da raiz do repositório, com credencial no `.env` (`OPENAI_API_KEY`, opcionalmente `LLM_MODEL`):

```sh
LOGISTICS_V3_DEMO=0 docker compose --env-file .env \
  -f studies/scenarios/logistics/v3/docker/compose.yaml up --build --wait -d
uv run --project sdk/python python -m studies.scenarios.logistics.v3.benchmarks.run --suite basic --cases easy
```

Serviços: `registry`, `orchestrator` (portas locais 55061/55062), `planner`
(LLM, capacidade `mission-planning`), `single-llm` (LLM, capacidade
`logistics-v3-single-llm`), `delivery-1`, `delivery-2`, `delivery-3` (BDI,
capacidade `logistics-v3-delivery`) e `execute` (determinístico, capacidade
`logistics-v3-execute`). Só os dois contêineres LLM recebem a chave. O
cliente roda no host e envia `RunMission` ao orquestrador; o laço da missão
acontece no Go.

Sem credencial, `LOGISTICS_V3_DEMO=1` no `up` e `--demo` no cliente usam os
substitutos determinísticos nos dois planejadores. Recrie os serviços ao
trocar modo ou modelo. Para encerrar:

```sh
docker compose -f studies/scenarios/logistics/v3/docker/compose.yaml down
```

[Estudo v3](../README.md)
