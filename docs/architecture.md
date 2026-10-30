# Arquitetura e conceitos

O contrato define a comunicação comum. O runtime coordena tarefas usando esse
contrato. Cada agente implementa seu próprio raciocínio de domínio.

## Componentes

| Componente | Responsabilidade | Código |
|---|---|---|
| Contrato | Mensagens e serviços gRPC compartilhados | [contract.proto](../proto/contract/v1/contract.proto) |
| Registry | Cadastro, descoberta por capacidade, heartbeat e detecção de falhas | [registry](../runtime/services/registry/cmd/main.go) |
| Orchestrator | Seleção, execução, retry, planejamento delegado e workflows | [orchestrator](../runtime/services/orchestrator/internal/server/server.go) |
| Messaging | Publicação e recebimento por destinatário, em memória | [messaging](../runtime/services/messaging/internal/server/server.go) |
| SDK Python | Modelos, registro, servidor do agente, heartbeat e clientes | [ariadne_sdk](../sdk/python/src/ariadne_sdk/__init__.py) |
| Agentes | Interpretação, planejamento de domínio e tarefas de teste | [catálogo](scenarios.md) |
| Eventos e análise | Registro da execução e extração de métricas | [logger](../runtime/services/internal/events/logger.go), [métricas](../tools/runtime_metrics/compute_metrics.py) |

O detector de falhas faz parte do processo Registry; não é um serviço separado.
Registry e workflows armazenam estado em memória. Os eventos são arquivos JSONL.

## Execução

Um experimento é um `scenario.py` que declara agentes e uma tarefa, um
workflow ou uma missão. `./ariadne run` gera um projeto Compose por execução:
três contêineres para os serviços Go e um contêiner por agente, com uma imagem
genérica que carrega o mesmo arquivo e serve o agente de índice N. O cliente
da amostra, no host, envia a tarefa ou missão ao Orchestrator e salva o
resultado junto aos eventos e logs. Detalhes no
[executor](cli.md) e em [experimentos](experiments.md).

## Tarefa simples

```mermaid
sequenceDiagram
    participant C as Cliente
    participant O as Orchestrator
    participant R as Registry
    participant A as Agente
    A->>R: Registro e heartbeats
    C->>O: SubmitTask
    O->>R: DiscoverAgents(capabilities)
    R-->>O: Agentes compatíveis
    O->>A: ExecuteTask
    A-->>O: TaskResult
    O-->>C: SubmitTaskResponse
```

O executor aplica seleção e timeout. Quando a política permite, uma falha
leva a nova descoberta e tentativa, podendo excluir agentes que já falharam.
O [executor](../runtime/services/orchestrator/internal/execution/executor.go)
é compartilhado por tarefas simples e etapas de workflows.

## Missão heterogênea

No cenário de rotas, o cliente envia um objetivo e um contexto com
`RunMission`. O orquestrador descobre um agente `mission-planning` e roda o
laço de missão:

1. O agente LLM planejador devolve um plano (passos, dependências, bindings).
2. O runtime valida o plano e o executa como workflow.
3. O agente BDI delibera e escolhe uma rota.
4. Um binding entrega o resultado à etapa LLM de explicação.
5. A rodada volta ao planejador, que responde `DONE` com a saída final.

O runtime também aceita um workflow definido pelo cliente, sem planner LLM.
Etapas independentes podem rodar em paralelo. A API assíncrona permite iniciar,
consultar e cancelar uma execução; o acompanhamento atual usa polling.

O cenário logístico híbrido usa um workflow explícito diferente: LLM interpreta
restrições e BDI planeja a missão. A simulação ocorre no domínio e no avaliador,
não como controle de um robô físico.

## Mensagens e workflows

Workflows chamam `AgentService.ExecuteTask` diretamente. A mensageria atende
outro caminho: um `MessagingClient` publica para um destinatário e outro recebe
por stream. Ela é complementar, sem ser pré-requisito para encadear tarefas.

## Glossário

| Termo | Significado neste projeto |
|---|---|
| Capability | Identificador de uma capacidade anunciada pelo agente e requerida pela tarefa |
| Task | Unidade de trabalho com objetivo, payload e campos operacionais |
| Workflow / step | Grafo de tarefas com dependências / uma etapa desse grafo |
| Binding | Cópia controlada de um campo do resultado anterior para o payload seguinte |
| Trace | Identificação usada para correlacionar a execução |
| Heartbeat | Atualização periódica da saúde e carga do agente |
| Retry / reassignment | Nova tentativa / nova atribuição após falha, conforme a política |
| BDI | Crenças, desejos e intenções; aqui, uma abstração simplificada em Python |
| LLM | Modelo usado por um agente para interpretação, planejamento estruturado ou explicação |

[Referência técnica](reference.md) · [Limitações](limitations.md) · [Índice](README.md)
