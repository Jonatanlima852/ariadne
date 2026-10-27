# Missão de rotas em contêineres

Topologia isolada para a missão `planejador LLM -> rota BDI -> explicação LLM`.
Execute os comandos a partir da raiz do repositório.

## Configuração

Copie o exemplo e preencha a chave localmente:

```sh
cp studies/scenarios/routing/docker/.env.example \
  studies/scenarios/routing/docker/.env
```

| Variável | Uso | Default |
|---|---|---:|
| `OPENAI_API_KEY` | credencial da Responses API; obrigatória | — |
| `LLM_MODEL` | modelo usado pelo agente LLM | `gpt-5.6-luna` |
| `ROUTING_DEMO` | `1` troca o modelo pelo substituto determinístico | `0` |
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

O executor roda o cliente [scenario.py](scenario.py) em contêiner, salva o
`MissionResult` em `.ariadne/runs/ID/result.json` e encerra os serviços. Há
chamadas reais à LLM. Veja [configuração e prazos](../../../../docs/cli.md).

## Execução manual (Python e uv no host)

```sh
docker compose \
  --env-file studies/scenarios/routing/docker/.env \
  -f studies/scenarios/routing/docker/compose.yaml \
  up --build -d --wait

ORCHESTRATOR_ADDR=localhost:50052 \
uv run --project sdk/python \
  python studies/scenarios/routing/docker/scenario.py
```

Com `ROUTING_DEMO=1` exportado antes do `up`, passe `--demo` ao cliente: ele
confere que os agentes LLM usaram o substituto. O relatório é salvo em
`studies/scenarios/routing/runtime_metrics/results/mission-result.json`.
Sem Docker, a mesma missão roda com `./ariadne run` (veja o
[README do cenário](../README.md)).

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

O cliente envia apenas o objetivo e o contexto (`origin`, `destination`,
`graph`) com `RunMission`. O Orchestrator pede o plano ao agente
`mission-planning`, executa o passo BDI, injeta o resultado por binding no
passo de explicação, devolve a rodada ao planejador e termina com `DONE`.
O cliente confere o resultado com `check_mission` (estado, agentes LLM e BDI,
rota `A -> B -> D` com distância 25 e rastro de deliberação).

[Catálogo de cenários](../../../../docs/scenarios.md)
