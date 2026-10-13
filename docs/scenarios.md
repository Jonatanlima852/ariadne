# Catálogo de cenários

Comece pelos casos determinísticos. Todos os cenários abaixo podem ser
executados pelo [executor tg](cli.md), com Docker e Compose >=2.24.4, sem
Python ou uv no host. Os READMEs também mantêm comandos manuais, que podem
exigir ferramentas adicionais. Execute da raiz do repositório.

| Cenário | O que observar | Requisitos adicionais via tg | Resultado esperado |
|---|---|---|---|
| [Echo básico](quickstart.md) | Descoberta e tarefa simples | Nenhum no caminho Docker | `COMPLETED`, agente `mock-agent-01` |
| [Workflow sequencial](../examples/docker/workflow-sequential/README.md) | Dependência `first → second` | Nenhum | Validação aprovada, saída `echo: second` |
| [Falha e reassignment](../examples/docker/failure-reassignment/README.md) | Timeout de `a-slow` e nova atribuição | Nenhum | Validação aprovada, agente `b-healthy` |
| [Mensageria](../examples/docker/messaging-basic/README.md) | Envelope e correlação preservados | Nenhum | Validação aprovada, mesmo message ID |
| [Rota heterogênea](../examples/docker/heterogeneous-route/README.md) | Planner LLM, rota BDI e explicação LLM | Chave e acesso ao modelo configurado | Rota `A → B → D`, distância 25 e relatório JSON |
| [Missão logística](../examples/docker/logistics-mission/README.md) | Interpretação LLM e plano BDI com restrições | Chave e acesso ao modelo configurado | Plano aceito pelo avaliador do domínio |

```sh
./tg scenario workflow-sequential
./tg scenario failure-reassignment
./tg scenario messaging-basic
```

O resumo aparece no terminal; a saída detalhada fica em `scenario.log` e o
resultado estruturado em `result.json`, dentro do diretório da execução.

## Como escolher

- Para estudar o runtime: echo, workflow e falha.
- Para estudar comunicação iniciada por agentes: mensageria.
- Para observar o raciocínio BDI sem serviços: [demo do agendador](../examples/support/agents/meeting-scheduler/demo.py).
- Para observar interoperabilidade LLM/BDI: rota heterogênea e missão logística.
- Para comparar resultados sistematicamente: [guia de avaliação](evaluation.md).

A demo do agendador roda com o ambiente do SDK:

```sh
uv run --directory sdk/python python ../../examples/support/agents/meeting-scheduler/demo.py
```

## Endereços e isolamento

Os endereços abaixo valem para os comandos Compose manuais. `./tg` remove as
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
reutiliza o Compose de benchmarks; não possui topologia independente.

Não envie tarefas de decomposição pelo cliente genérico esperando que ele
mostre um workflow. Use o script da rota heterogênea ou `RuntimeClient` do SDK.

[Índice](README.md)
