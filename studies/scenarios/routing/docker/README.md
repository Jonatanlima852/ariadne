# Cenário heterogêneo de rotas

Topologia isolada para o workflow automático `LLM -> BDI -> LLM`. Execute os
comandos a partir da raiz do repositório.

## Configuração

Copie o exemplo e preencha a chave localmente:

```sh
cp studies/scenarios/routing/docker/.env.example \
  studies/scenarios/routing/docker/.env
```

Variáveis:

| Variável | Uso | Default |
|---|---|---:|
| `OPENAI_API_KEY` | credencial da Responses API; obrigatória | — |
| `LLM_MODEL` | modelo usado pelo agente LLM | `gpt-5.6-luna` |
| `REGISTRY_PORT` | Registry no host | `50051` |
| `ORCHESTRATOR_PORT` | Orchestrator no host | `50052` |
| `BDI_AGENT_PORT` | agente BDI no host | `60054` |
| `LLM_AGENT_PORT` | agente LLM no host | `60056` |

O arquivo `.env` é ignorado pelo Git. Nunca coloque a chave no Compose,
Dockerfile ou relatório do cenário.

## Execução

Com Docker e Compose >=2.24.4 e a chave configurada acima:

```sh
./ariadne doctor heterogeneous-route
./ariadne scenario heterogeneous-route
```

O executor roda também o cliente em contêiner, salva o relatório em
`.ariadne/runs/ID/result.json` e encerra os serviços. Há chamadas reais à LLM.
Veja [configuração e prazos](../../../../docs/cli.md).

## Execução manual (Python e uv no host)

```sh
docker compose \
  --env-file studies/scenarios/routing/docker/.env \
  -f studies/scenarios/routing/docker/compose.yaml \
  up --build -d --wait

ORCHESTRATOR_ADDR=localhost:50052 \
uv run --project sdk/python \
  python studies/scenarios/routing/scenario.py
```

O relatório é salvo em `studies/scenarios/routing/runtime_metrics/results/heterogeneous-report.json`.

## Logs e limpeza

```sh
docker compose \
  --env-file studies/scenarios/routing/docker/.env \
  -f studies/scenarios/routing/docker/compose.yaml logs -f

docker compose \
  --env-file studies/scenarios/routing/docker/.env \
  -f studies/scenarios/routing/docker/compose.yaml down
```

Use `down -v` somente quando também quiser apagar os eventos. O nome de
projeto `ariadne-heterogeneous-route` mantém rede e volume separados do Compose
baseline em `tools/deploy/`.

O cliente envia somente a pergunta com a capability `task-decomposition`. O
Orchestrator solicita o DAG ao agente LLM, valida-o, executa o agente BDI,
injeta o resultado por bindings no step de explicação e agrega a resposta. O
relatório inclui `workflow_id`, `run_id`, métricas de duração e resultados por
step.

[Catálogo de cenários](../../../../docs/scenarios.md)
