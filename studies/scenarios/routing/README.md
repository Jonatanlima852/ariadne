# Rotas

Missão didática de cooperação heterogênea: o cliente entrega um objetivo que
não sabe decompor, um agente LLM planeja, um agente BDI deliberativo escolhe
a rota e o mesmo LLM a explica. O exemplo espera `A -> B -> D`, distância 25.

## Pergunta

Agentes com arquiteturas diferentes cooperam numa missão coordenada pelo
orquestrador, sem se chamarem diretamente?

## Como funciona

Duas rodadas do laço de missão:

1. O Orchestrator envia `PlannerRequest` (objetivo, contexto com origem,
   destino e mapa, capacidades disponíveis) ao agente `mission-planning`.
2. Rodada 1, `PLAN`: passo `route` (`route-planning`) e passo `explain`
   (`explanation`), que depende de `route` e recebe sua saída por binding.
3. O BDI forma crenças a partir do payload, delibera entre `direct_route` e
   `via_intermediate`, executa a busca e devolve rota, distância e o rastro.
4. A LLM explica a rota recebida.
5. Rodada 2, `DONE`: o planejador copia `{route, distance, explanation}` do
   histórico para a saída da missão.

- [scenario.py](scenario.py): `Scenario(mission=Mission(...))`, com rótulos de
  apresentação para o Mission Viewer.
- [mission.py](mission.py): objetivo, contexto e verificação do resultado.
- [agents/route_planner](agents/route_planner/README.md): BDI deliberativo.
- [agents/planner_explainer](agents/planner_explainer/README.md): planejador e explicação.

## Executar

```sh
ROUTING_DEMO=1 ./ariadne run studies/scenarios/routing/scenario.py   # sem credencial
export OPENAI_API_KEY=...
./ariadne run studies/scenarios/routing/scenario.py                  # modelo real
```

O `mission-result.json` em `runs/` é o `MissionResult` do contrato; abra-o
com `./ariadne viewer`.

## Variáveis

| Variável | Padrão | Efeito |
|---|---|---|
| `ROUTING_DEMO` | `0` | `1` troca o modelo pelo substituto determinístico no planejador e na explicação |
| `LLM_MODEL` | `gpt-5.6-luna` | Modelo pedido ao provedor no modo real |

## Limites

Não representa uma missão logística com bateria, pacotes ou prazo; essas
regras pertencem a [logistics](../logistics/README.md). O substituto serve a
testes e demonstrações, não é uma linha de base. Os testes em
[test_agents.py](test_agents.py) cobrem os agentes sem runtime e
[test_mission.py](test_mission.py) roda a missão em contêineres
(`ARIADNE_TEST_DOCKER=1`).

[Todos os estudos](../../README.md)
