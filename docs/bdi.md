# BDI declarativo e planejamento

`BdiAgent` recebe crenças, desejo e planos. O SDK resolve as entradas, avalia
alternativas, seleciona uma intenção e executa somente o plano escolhido.
Nenhuma subclasse ou mensagem protobuf é necessária.

```python
from ariadne_sdk import BdiAgent, Input, Plan, Scenario, Step

agent = BdiAgent(
    name="routes", capabilities=["route"],
    beliefs=Input("world"), desire=Input("destination"),
    plans=[Plan("direct", execute=lambda world, destination: {
        "route": [world["start"], destination],
    })],
)
scenario = Scenario(agents=[agent], tasks=[
    Step("route", "Ir de A para D", payload={"world": {"start": "A"}, "destination": "D"}),
])
```

Salve como um arquivo Python e execute com `./ariadne run caminho.py`. Este exemplo
apenas compõe uma rota; restrições e disponibilidade de conexões são regras do
domínio. Consulte a [fixture de seleção de planos](../sdk/python/tests/fixtures/route_choice.py),
[agendamento](../studies/scenarios/meeting/scenario.py) e [logística](../studies/scenarios/logistics/agents/mission_planner.py).

## Entradas e estado

- `Input("world")` lê um campo obrigatório de `Task.payload`.
- `Input("mission", "destination")` lê campos aninhados, sem interpretar pontos
  dentro das chaves. `Input()` lê o payload inteiro.
- `Input("options", default={})` usa o padrão somente quando o campo falta.
  `None`, `False`, zero e coleções vazias são valores presentes.
- `beliefs` e `desire` também aceitam valores literais ou uma função `Task -> valor`.
  Por exemplo, `desire=lambda task: task.goal` usa o objetivo textual.
- Sem configuração, crenças são `{}` e desejo é o payload inteiro.

O SDK faz cópias profundas das entradas por tarefa. Alterações feitas por um
plano não modificam o payload recebido nem crenças compartilhadas entre tarefas.
Não há atualização persistente automática, mesclagem implícita de `Task.bdi`,
replanejamento contínuo ou reserva automática de recursos externos. Para estado
persistente, use um serviço de domínio com controle explícito de concorrência.
Um campo ausente resulta em `ERROR_CODE_INVALID_TASK`; validações semânticas,
como duração positiva de uma reunião, pertencem ao domínio.

## Planos e seleção

```python
Plan("deliver", when=can_deliver, cost=estimate_cost, execute=deliver)
```

Todos os callbacks recebem **`(beliefs, desire)`**, nessa ordem. `when` e `cost`
devem ser funções puras: não executam ações nem modificam entradas. `execute`
pode produzir efeitos e devolve um dicionário, que vira integralmente o output;
chaves como `name`, `cost` e `output` não são reservadas nesse dicionário.

`when` é opcional; sem ele o plano é aplicável. `cost` pode ser número finito ou
função; só é calculado se o plano for aplicável. A seleção segue:

1. Se houver candidatos com custo, escolhe o menor custo.
2. Em empate, prefere maior `priority` (padrão zero).
3. Persistindo empate, usa a ordem de declaração.
4. Planos sem custo são fallbacks; só competem quando nenhum aplicável tem custo.

Somente um `execute` é chamado. Se ele falhar, o SDK registra a falha; não tenta
executar outro plano implicitamente. Retry continua responsabilidade da política
da tarefa no runtime e pode repetir efeitos. Se nenhum plano for aplicável,
a tarefa falha com `ERROR_CODE_EXECUTION_FAILED`. Uma rejeição de domínio como
`{"feasible": False}` pode ser devolvida normalmente como tarefa concluída.

O resultado registra `selected_plan`, `evaluated_plans`, custos, prioridades e
uma descrição da regra de seleção. Erros durante avaliação/execução preservam
as decisões já tomadas, a fase e o tipo do erro. Isso descreve a decisão do
algoritmo, sem inventar justificativas de domínio. Entrada/saída completas e
trace ficam nas evidências do executor; gráficos continuam na avaliação offline.

## Planejamento por busca

BDI seleciona planos de uma biblioteca. Um plano pode usar busca para construir
uma sequência de ações; essas duas operações são separadas no SDK:

```python
from ariadne_sdk import SearchProblem, uniform_cost_search

edges = {"A": [("D", 30), ("B", 10)], "B": [("D", 15)]}
result = uniform_cost_search(SearchProblem(
    initial="A",
    actions=lambda state: edges.get(state, []),
    transition=lambda state, action: action[0],
    is_goal=lambda state: state == "D",
    cost=lambda state, action, next_state: action[1],
))
assert result.cost == 25
```

O domínio fornece estados hashable, ações possíveis, transições, condição de
objetivo e custo incremental. A transição pode retornar `None` para rejeitar
uma ação. Custos devem ser finitos e não negativos; o padrão é um por ação.
Estados iguais devem representar futuros equivalentes: inclua bateria, visitas
obrigatórias e demais recursos relevantes no estado. Callbacks devem ser puros.
A ordem das ações desempata caminhos de mesmo custo de forma determinística.

`SearchResult` contém `found`, `state`, `actions` (tupla), `cost` e `expanded`.
Sem solução após esgotar a fronteira, retorna `found=False`, estado inicial,
ações vazias e custo `None`. O SDK não executa as ações encontradas.

O padrão de `max_expansions` é 100.000 estados. Ao excedê-lo, lança
`SearchLimitExceeded`, que o agente registra como falha operacional. Isso não
significa que a missão seja impossível. O limite não é timeout nem limite de
memória; geradores de ações devem terminar e a tarefa continua sujeita aos
prazos do runtime. Um estado inicial que já satisfaz o objetivo exige zero
expansões.

A [logística](../studies/scenarios/logistics/domain/planning.py) usa esse algoritmo com suas
precondições e efeitos. O avaliador offline conserva sua busca de referência;
as duas implementações ainda compartilham as regras de domínio. Testes comparam
os oito casos e variações de prazo, sem alegar independência completa do oráculo.

## Compatibilidade e escopo

Subclasses com `desire`/`extract_desire`, `@plan` e `plan_library` continuam
funcionando. Nessa API histórica, as funções recebem **`(desire, beliefs)`**,
calculam candidatos com metadados e são todas chamadas durante a deliberação.
Elas não devem produzir efeitos externos. `select_plan`/`deliberate` pertencem
a esse caminho legado. Não combine `plans` com `plan_library`.

Para migrar, declare entradas com `Input`, leve condições para `when`, custo
para `cost` e efeitos para `execute`. Código que precisa calcular propostas
complexas deve mantê-las sem efeitos durante avaliação; um planejador também
pode ser chamado dentro do único plano aplicável, como no estudo logístico.

Esta é uma abstração BDI orientada a tarefas, com crenças, desejo e intenção
selecionada. Não implementa um interpretador AgentSpeak nem um agente autônomo
com ciclo contínuo de percepção e revisão de objetivos.

[Experimentos](experiments.md) · [Desenvolvimento](development.md)
