# Catálogo de cenários

Todos os cenários são declarações `scenario.py` executadas por
`./ariadne run`, que sobe serviços e agentes em contêineres. Comece pelos
casos determinísticos; só rotas, logística e saudação podem chamar um modelo.
Execute da raiz do repositório.

| Cenário | O que observar | Comando | Resultado esperado |
|---|---|---|---|
| [Tarefa simples](../studies/scenarios/basic_task/README.md) | Descoberta e tarefa simples | `./ariadne run studies/scenarios/basic_task/scenario.py` | `WORKFLOW_STATUS_COMPLETED`, texto ecoado |
| [Workflow sequencial](../studies/scenarios/sequential_workflow/README.md) | Dependência `first → second` e binding | `./ariadne run studies/scenarios/sequential_workflow/scenario.py` | Saída `OLÁ, AGENTES!` |
| [Falha e reassignment](../studies/scenarios/failure_reassignment/README.md) | Timeout de `a-slow` e nova atribuição | `./ariadne run studies/scenarios/failure_reassignment/scenario.py` | Concluído por `b-healthy`; `TASK_TIMEOUT` e `TASK_REASSIGNED` nos eventos |
| [Mensageria](../studies/scenarios/messaging/README.md) | Envelope publicado por um agente e recebido por outro | `./ariadne run studies/scenarios/messaging/scenario.py` | `matches_sent: true`, mesmo message ID |
| [Seleção de agentes](../studies/scenarios/agent_selection/README.md) | Políticas de seleção entre três agentes | `AGENT_SELECTION_POLICY=LEAST_LOADED ./ariadne run studies/scenarios/agent_selection/scenario.py` | Distribuição conforme a política |
| [Agendamento BDI](../studies/scenarios/meeting/README.md) | Crenças, restrições e planos | `./ariadne run studies/scenarios/meeting/scenario.py` | Horário `start: 12` |
| [Saudação LLM](../studies/scenarios/greeting/README.md) | Resposta estruturada de um provedor | `ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/greeting/scenario.py` | Saudação validada pelo esquema |
| [Rota heterogênea](../studies/scenarios/routing/README.md) | Missão: planejador LLM, rota BDI deliberativa e explicação LLM | `ROUTING_DEMO=1 ./ariadne run studies/scenarios/routing/scenario.py` (sem chave) | Rota `A → B → D`, distância 25, `MissionResult` em JSON |
| [Fan-out](../studies/scenarios/fanout/README.md) | N passos de mapa em paralelo, prazo estourado e reatribuição | `./ariadne run studies/scenarios/fanout/scenario.py` | `MISSION_STATUS_COMPLETED`, um passo reatribuído |
| [Logística v3](../studies/scenarios/logistics/v3/README.md) | Missão com planejador LLM, entregadores BDI e executor | `LOGISTICS_V3_DEMO=1 ./ariadne run studies/scenarios/logistics/v3/scenario.py` | Pedidos entregues, incidentes tratados em novas rodadas |
| [Logística v1](../studies/scenarios/logistics/README.md) | Workflow fixo: interpretação LLM e plano BDI | `ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py` | Plano aceito pelo avaliador do domínio |

O resumo aparece no terminal; o resultado estruturado fica em `result.json`
(e `mission-result.json` para missões) dentro do diretório da execução.

## Como escolher

- Para estudar o runtime: tarefa simples, workflow e falha.
- Para estudar comunicação iniciada por agentes: mensageria.
- Para observar o raciocínio BDI: agendamento.
- Para observar o laço de missão sem credencial: rotas com `ROUTING_DEMO=1`
  e logística v3 com `LOGISTICS_V3_DEMO=1`.
- Para ver paralelismo e reatribuição num Gantt: fan-out.
- Para observar interoperabilidade LLM/BDI com um modelo real: exporte
  `OPENAI_API_KEY` e rode rotas ou logística v3 sem a variável de demonstração.
- Para comparar resultados sistematicamente: [guia de avaliação](evaluation.md).

Cada execução cria um projeto Compose exclusivo, sem portas fixas; duas
execuções podem rodar ao mesmo tempo. Veja a [referência do executor](cli.md).

[Índice](README.md)
