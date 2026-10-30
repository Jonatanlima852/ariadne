# Catálogo de cenários

Comece pelos casos determinísticos. Todos os cenários abaixo podem ser
executados pelo [executor ariadne](cli.md), com uv e Docker Compose >=2.24.4.
O uv prepara o Python da CLI; Go não é necessário no host. Os READMEs também mantêm comandos manuais, que podem
exigir ferramentas adicionais. Execute da raiz do repositório.

| Cenário | O que observar | Requisitos adicionais via ariadne | Resultado esperado |
|---|---|---|---|
| [Echo básico](quickstart.md#alternativa-com-docker) | Descoberta e tarefa simples | Nenhum no caminho Docker | `COMPLETED`, agente `execution-simulator-01` |
| [Workflow sequencial](../studies/scenarios/sequential_workflow/docker/README.md) | Dependência `first → second` | Nenhum | Validação aprovada, saída `echo: second` |
| [Falha e reassignment](../studies/scenarios/failure_reassignment/docker/README.md) | Timeout de `a-slow` e nova atribuição | Nenhum | Validação aprovada, agente `b-healthy` |
| [Mensageria](../studies/scenarios/messaging/docker/README.md) | Envelope e correlação preservados | Nenhum | Validação aprovada, mesmo message ID |
| [Rota heterogênea](../studies/scenarios/routing/docker/README.md) | Missão: planejador LLM, rota BDI deliberativa e explicação LLM | Chave e acesso ao modelo configurado; sem chave, `ROUTING_DEMO=1 ./ariadne run studies/scenarios/routing/scenario.py` | Rota `A → B → D`, distância 25, rastro BDI e `MissionResult` em JSON |
| [Missão logística](../studies/scenarios/logistics/docker/README.md) | Interpretação LLM e plano BDI com restrições | Chave e acesso ao modelo configurado | Plano aceito pelo avaliador do domínio |
| [Fan-out](../studies/scenarios/fanout/README.md) | N passos de mapa em paralelo, prazo estourado e reatribuição, rastro completo | Nenhum: `./ariadne run studies/scenarios/fanout/scenario.py` | `COMPLETED`, um passo com tentativa 2 em outro contador, `TASK_TIMEOUT` e `TASK_REASSIGNED` nos eventos |

```sh
./ariadne scenario workflow-sequential
./ariadne scenario failure-reassignment
./ariadne scenario messaging-basic
```

O resumo aparece no terminal; a saída detalhada fica em `scenario.log` e o
resultado estruturado em `result.json`, dentro do diretório da execução.

## Como escolher

- Para estudar o runtime: echo, workflow e falha.
- Para estudar comunicação iniciada por agentes: mensageria.
- Para observar o raciocínio BDI sem Docker: [cenário de agendamento](../studies/scenarios/meeting/scenario.py).
- Para observar o laço de missão sem credencial: [rotas](../studies/scenarios/routing/README.md) com `ROUTING_DEMO=1`.
- Para ver paralelismo e reatribuição num Gantt: [fan-out](../studies/scenarios/fanout/README.md), sem credencial.
- Para observar interoperabilidade LLM/BDI: rota heterogênea e missão logística.
- Para comparar resultados sistematicamente: [guia de avaliação](evaluation.md).

O cenário de agendamento usa o SDK e inicia o runtime local:

```sh
./ariadne run studies/scenarios/meeting/scenario.py
```

## Endereços e isolamento

Os endereços abaixo valem para os comandos Compose manuais. `./ariadne` remove as
portas publicadas e usa exclusivamente a rede interna de cada execução.

| Topologia | Endereço de entrada padrão no host |
|---|---|
| Básica e rota heterogênea | Orchestrator `localhost:50052` |
| Falha | Orchestrator `localhost:52052` |
| Workflow sequencial | Orchestrator `localhost:53052` |
| Benchmarks e missão logística | Orchestrator `localhost:54052` |
| Mensageria isolada | Messaging `localhost:55053` |

A básica e a rota heterogênea compartilham portas padrão: encerre uma antes
de iniciar a outra ou configure as portas do cenário. A missão logística
possui Compose próprio em `studies/scenarios/logistics/docker/compose.yaml` e
compartilha a porta padrão com a comparação A–D.

A rota heterogênea é uma missão: use `./ariadne run` com a declaração do
cenário, o cliente Docker do cenário ou `RuntimeClient.run_mission` do SDK.

[Índice](README.md)
