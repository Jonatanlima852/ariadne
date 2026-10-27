# Logística v3: o estudo como missão

A v3 responde à crítica feita à v2: o laço de episódio saiu do controlador
Python e passou a ser o laço de missão do orquestrador Go (contrato 2.0.0).
O domínio (estado, transições, incidentes, métricas) e os casos são os da
[v2](../v2/README.md), importados sem alteração. Duas configurações rodam
como missões e compartilham runtime, evidências e visualizador:

| Configuração | Planejador (capacidade) | Passos de cada rodada |
|---|---|---|
| `ariadne-v3` | LLM `mission-planning` | um `plan-delivery` por pedido atacado agora (agentes BDI `logistics-v3-delivery`, em paralelo) e um `execute` final (`logistics-v3-execute`) que recebe as propostas por bindings |
| `single-llm-v3` | LLM `logistics-v3-single-llm` (mesmo prompt da v2) | um único `execute` com as ações que o modelo decidiu |

O planejador LLM interpreta os pedidos em linguagem natural, decide quais
atacar em paralelo e com que veículo, e replaneja ao ver no contexto o novo
estado e os incidentes que o executor disparou. Cada entregador BDI delibera
sobre um pedido (`direct_delivery`, `load_from_other_depot`,
`recharge_then_deliver`, `continue_with_cargo`,
`transfer_from_disabled_vehicle`) usando as buscas da v2 e devolve a
sequência de ações proposta com o rastro; um pedido inviável volta como
`feasible=false` com o motivo. O executor aplica as propostas na ordem do
plano, rejeita ações inválidas e dispara incidentes antes da próxima ação.

| Caminho | Responsabilidade |
|---|---|
| `domain/` | Adaptadores do domínio da v2 ao laço de missão e leitura dos casos |
| `agents/` | `planner` (LLM), `single_llm` (LLM), `delivery` (BDI), `execute` (determinístico), cada um com Dockerfile |
| `mission.py` | Declaração da missão por caso/configuração e métricas do `MissionResult` |
| `scenario.py` | Um caso como missão declarada com processos locais |
| [benchmarks/](benchmarks/run.py) | Coletor contra o Compose, `analyze.py` reutilizando a v2 |
| [docker/](docker/README.md) | Topologia: Registry, Orchestrator, 2 planejadores LLM, 3 entregadores, executor |
| `tests/` | Agentes sem runtime, laço imitado e integração com os binários Go |

Da raiz, sem credencial (substitutos determinísticos; não mede um modelo):

```sh
LOGISTICS_V3_DEMO=1 LOGISTICS_V3_CASE=vehicle-loss ./ariadne run studies/scenarios/logistics/v3/scenario.py
LOGISTICS_V3_DEMO=1 LOGISTICS_V3_CONFIGURATION=single-llm-v3 ./ariadne run studies/scenarios/logistics/v3/scenario.py
```

Campanha real, com `.env` contendo `OPENAI_API_KEY` (e `LLM_MODEL` opcional):

```sh
LOGISTICS_V3_DEMO=0 docker compose --env-file .env \
  -f studies/scenarios/logistics/v3/docker/compose.yaml up --build --wait -d
uv run --project sdk/python python -m studies.scenarios.logistics.v3.benchmarks.run \
  --suite stress --configurations ariadne-v3 single-llm-v3 --repeat 3
python -m studies.scenarios.logistics.v3.benchmarks.analyze \
  --input .ariadne/logistics-v3/<coleta>/results.json --output /tmp/logistics-v3-analysis --no-plots
```

Cada missão fica em `missions/<caso>-<configuração>-r<n>.json`, o
`MissionResult` do contrato, legível no
[visualizador de missão](../../../../tools/mission-viewer/README.md).
Testes sem LLM e sem Docker: `tests/test_agents.py`; com os binários Go,
`ARIADNE_TEST_RUNTIME_DIR=.ariadne/bin` e `tests/test_mission.py`.

[Estudo logístico](../README.md)
