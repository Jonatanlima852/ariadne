# Rotas

Exemplo didático de cooperação entre agentes heterogêneos numa missão: o
cliente entrega um objetivo que não sabe decompor, um agente LLM planeja, um
agente BDI deliberativo escolhe a rota e o mesmo agente LLM a explica. O
exemplo espera `A -> B -> D`, distância 25. Não representa uma missão
logística com bateria, pacotes ou prazo; essas regras pertencem a
[logistics](../logistics/README.md).

Fluxo de uma execução (duas rodadas do laço de missão):

1. O Orchestrator envia `PlannerRequest` (objetivo, contexto com origem,
   destino e mapa, capacidades disponíveis) ao agente `mission-planning`.
2. Rodada 1, `PLAN`: passo `route` (`route-planning`) e passo `explain`
   (`explanation`), que depende de `route` e recebe sua saída por binding.
3. O BDI forma crenças a partir do payload, delibera entre `direct_route` e
   `via_intermediate`, executa a busca e devolve rota, distância e o rastro.
4. A LLM explica a rota recebida.
5. Rodada 2, `DONE`: o planejador copia `{route, distance, explanation}` do
   histórico para a saída da missão.

- [scenario.py](scenario.py): declaração `Scenario(mission=Mission(...))`.
- [mission.py](mission.py): objetivo, contexto e verificação do resultado.
- [agents/route_planner](agents/route_planner/README.md): BDI deliberativo.
- [agents/planner_explainer](agents/planner_explainer/README.md): planejador e explicação.
- [docker](docker/README.md): topologia em contêineres e cliente `run_mission`.
- [benchmarks](benchmarks/README.md): medição C, dentro deste assunto.

Da raiz, sem credencial (substituto determinístico do modelo):

```sh
ROUTING_DEMO=1 ./ariadne run studies/scenarios/routing/scenario.py
```

Com a credencial LLM configurada (`OPENAI_API_KEY`, opcionalmente `LLM_MODEL`):

```sh
./ariadne run studies/scenarios/routing/scenario.py
./ariadne scenario heterogeneous-route
```

O `mission-result.json` gravado nas evidências é o `MissionResult` do
contrato; abra-o no [visualizador de missão](../../../tools/mission-viewer/README.md).
Os testes em [test_agents.py](test_agents.py) cobrem os agentes sem runtime
e [test_mission.py](test_mission.py) roda a missão com os binários Go
(`ARIADNE_TEST_RUNTIME_DIR`).

[Todos os estudos](../../README.md)
