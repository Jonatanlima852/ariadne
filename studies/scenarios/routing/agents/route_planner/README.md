# Planejador de rotas

Agente BDI deliberativo do SDK (`BdiAgent` com `GoalPlan`), capacidade
`route-planning`. Implementação em [main.py](main.py). O ID padrão é
`route-planner-01`; cenários podem configurar `AGENT_ID`.

- Crenças: nascem do payload da tarefa (`origin`, `destination`, `graph`,
  `max_stops`, padrão 1) e morrem com ela. Sem `graph`, usa o mapa do exemplo.
- Objetivo: `plan_route`, fixo no agente.
- Planos: `direct_route` (contexto: existe ligação direta; custo: a distância)
  e `via_intermediate` (contexto: há outro trecho saindo da origem; custo
  estimado: o menor primeiro trecho). O corpo de `via_intermediate` executa
  `act(find_route)`, uma busca de custo uniforme limitada a `max_stops` escalas,
  e registra `observe(stops=...)`.
- Resultado: `route` e `distance` na saída; `selected_plan` e `bdi_trace`
  (ciclos, crenças adicionadas, ação e desfecho) em `metadata` e `TaskResult.bdi`.

Para A -> D no mapa do exemplo, a ligação direta custa 30 e o plano com
escala estima 10, então ele é escolhido e encontra A -> B -> D (25). Sem plano
aplicável (origem desconhecida) a tarefa falha e a decisão volta ao
planejador da missão.

[Cenário proprietário](../../README.md)
