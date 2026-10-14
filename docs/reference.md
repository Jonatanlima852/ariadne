# Contrato e configuração

## Versão e fonte de verdade

O [contract.proto](../proto/contract/v1/contract.proto) define os campos e RPCs
executáveis. A versão está em [VERSION](../proto/contract/v1/VERSION): `1.0.0`.
O Registry verifica o major declarado pelo agente; o SDK usa `1.0.0` por padrão.
Consulte a [validação de versão](../runtime/contractversion/version.go).

Para conferir o checksum sem compilar nem regenerar arquivos:

```sh
sh tools/check-contract-freeze.sh
```

A adoção do nome Ariadne alterou somente a opção de geração Go para
`ariadne/runtime/gen/go/contract/v1;contractv1` e o comentário de identificação.
Os stubs foram regenerados; a comparação dos descritores confirmou que campos,
números, mensagens e RPCs permanecem iguais. O checksum foi atualizado para
essa mudança de identidade, mantendo a versão de comunicação `1.0.0`.

O pacote Python é versionado separadamente do contrato. Sua versão `0.1.0`
não altera o major protobuf anunciado pelos agentes.

## Serviços disponíveis

| Serviço | RPCs |
|---|---|
| `RegistryService` | `RegisterAgent`, `UnregisterAgent`, `GetAgent`, `DiscoverAgents`, `ReportHealth` |
| `AgentService` | `ExecuteTask` |
| `OrchestratorService` | `SubmitTask`, `SubmitWorkflow`, `StartWorkflow`, `GetWorkflow`, `CancelWorkflow` |
| `MessagingService` | `PublishMessage`, `StreamMessages` |

`SubmitTaskResponse` pode conter `result`, `workflow_result` ou um erro
operacional. A API `RuntimeClient` do SDK distingue esses resultados. O cliente
genérico de terminal atualmente só apresenta tarefas simples.

Não há `WatchWorkflow` no contrato atual. O acompanhamento assíncrono usa
`GetWorkflow`. Saúde é reportada ao Registry; `AgentService` não expõe um RPC
separado `GetHealth`.

## Entidades principais

| Entidade | Uso |
|---|---|
| `AgentDescriptor`, `Capability` | Identidade, endpoint e capacidades anunciadas |
| `Task`, `TaskResult` | Entrada e resultado da unidade de trabalho |
| `RetryPolicy`, `SelectionPolicy` | Regras de tentativas e seleção |
| `BdiExtension`, `LlmExtension` | Campos opcionais específicos de agentes |
| `WorkflowDefinition`, `WorkflowStep`, `ResultBinding` | Etapas, dependências e transferência de dados |
| `WorkflowResult`, `WorkflowStepResult` | Estado e resultados agregados |
| `HealthStatus` | Saúde, heartbeat e carga |
| `MessageEnvelope`, `MessageAck` | Comunicação por destinatário |
| `TraceContext`, `ErrorInfo`, `TaskEvent` | Correlação, erros e vocabulário de eventos |

Os envelopes são tipados; payloads e outputs de domínio usam estruturas
flexíveis. Um resultado `COMPLETED` indica conclusão operacional: no domínio
logístico, ele pode conter a rejeição correta de uma missão impossível.

## Políticas e limites

- `FIRST_AVAILABLE`: primeiro candidato na ordem estável de descoberta.
- `ROUND_ROBIN`: alternância por conjunto de agentes compatíveis.
- `LEAST_LOADED`: menor carga, depois quantidade de tarefas e ID como desempate.
- `RANDOM`: escolha aleatória entre candidatos.

Os nomes acima são as opções atuais; `LOWEST_LOAD` e `CAPABILITY_SCORE` não
são opções do enum implementado. Consulte o
[seletor](../runtime/services/orchestrator/internal/selection/policy.go).

Sem retry policy, há uma tentativa. `max_attempts` conta todas as tentativas,
incluindo a primeira. `Task.deadline_ms` é timeout por tentativa, não timestamp
absoluto. Zero usa `EXECUTION_TIMEOUT`. `exclude_failed_agent` controla a
exclusão de agentes entre tentativas.

O validator de workflow usa, por padrão, no máximo 10 steps, profundidade 5 e
payload de 64 KiB. O engine usa paralelismo 4 e timeout global de 30 segundos
por padrão. Esses valores são defaults do código, não variáveis de ambiente
expostas pelo serviço. Consulte [validator](../runtime/services/orchestrator/internal/workflow/validator.go)
e [engine](../runtime/services/orchestrator/internal/workflow/engine.go).

Bindings leem `output`, `metadata`, `status` ou `agent_id` de etapas ancestrais
e preenchem campos permitidos do payload. Não avaliam código ou expressões.

## Configuração operacional

Valores abaixo são defaults do processo/SDK; cada Compose pode sobrescrevê-los.

| Variável | Contexto | Default |
|---|---|---|
| `REGISTRY_ADDR` | Endereço de escuta do Registry | `:50051` |
| `REGISTRY_ADDR` | Destino usado pelo Orchestrator/SDK | `localhost:50051` |
| `ORCHESTRATOR_ADDR` | Escuta do Orchestrator | `:50052` |
| `EXECUTION_TIMEOUT` | Timeout por tentativa no Orchestrator | `30s` |
| `FAILURE_SCAN_INTERVAL` | Varredura do Registry | `1s` |
| `SUSPECTED_TIMEOUT` | Ausência de heartbeat até suspeita | `10s` |
| `DEAD_TIMEOUT` | Ausência de heartbeat até morte | `20s` |
| `HEARTBEAT_INTERVAL_SECONDS` | Intervalo do SDK | `5` |
| `AGENT_HOST` | Host anunciado por `Agent.from_env()` | `localhost` |
| `AGENT_PORT` | Porta de `Agent.from_env()` | Default da subclasse ou `60051` |
| `AGENT_ID`, `AGENT_NAME` | Identidade por `Agent.from_env()` | Defaults da subclasse ou nome da classe |
| `LLM_MODEL` | Modelo do agente LLM | `gpt-5.6-luna`, configuração atual do projeto |
| `OPENAI_API_KEY` | Credencial das execuções LLM reais | Sem default |

`EVENTS_PATH` define o arquivo JSONL. No Compose básico, o Orchestrator usa
`/data/events.jsonl` e Messaging usa `/data/message-events.jsonl`. O endereço
de um cliente no host é diferente do DNS entre contêineres; confira o
[catálogo de portas](scenarios.md#endereços-e-isolamento).

O modelo configurado deve estar acessível à conta usada. Os testes unitários
injetam clientes falsos e não verificam disponibilidade do provedor.

[Desenvolvimento](development.md) · [Índice](README.md)
