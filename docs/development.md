# Desenvolvimento

## Requisitos por atividade

| Atividade | Ferramentas |
|---|---|
| Cenários Docker via `./ariadne` | uv e Docker Compose >=2.24.4 |
| SDK, scripts e cenários Python | uv e Python compatível com o projeto |
| Compilar e testar o runtime localmente | Go 1.26.3 ou compatível com `runtime/go.mod` |
| Regenerar contrato | Go, protoc, plugins Go, uv e grpcio-tools |

Os projetos Python declaram Python >=3.11. O SDK possui `.python-version` com
3.14; uv pode selecionar ou baixar esse interpretador. Os Dockerfiles usam
versões próprias. Consulte [pyproject.toml](../sdk/python/pyproject.toml),
[.python-version](../sdk/python/.python-version) e [go.mod](../runtime/go.mod).

## Mapa do repositório

| Diretório | Conteúdo e ponto de entrada |
|---|---|
| `proto/` | [Contrato](../proto/contract/v1/contract.proto), versão e checksum |
| `runtime/` | Módulo Go, serviços e stubs gerados |
| `sdk/python/` | [API pública](../sdk/python/src/ariadne_sdk/__init__.py) e testes |
| `studies/scenarios/*/agents/` | Mock, echo, falha, rotas BDI, agendador BDI e LLM |
| `tools/clients/submit-task/` | [Cliente de tarefa simples](../tools/clients/submit-task/main.py) |
| `studies/scenarios/*/docker/` | Scripts de integração e topologias de cada cenário |
| `studies/scenarios/` | Cenários, regras, dados e avaliações próprios |
| `studies/scenarios/logistics/` | [Estudo declarativo](../studies/scenarios/logistics/README.md), agentes, domínio, dataset e avaliação offline |
| `studies/scenarios/logistics/v2/` | [Episódios com múltiplos pedidos](../studies/scenarios/logistics/v2/README.md), agentes especialistas e evidências preservadas |
| `studies/scenarios/logistics/v2/benchmarks/` | [Campanhas, arquivamento e análise](../studies/scenarios/logistics/v2/benchmarks/README.md) da v2 |
| `studies/scenarios/*/benchmarks/` | Campanhas, resultados selecionados e gráficos |
| `tools/runtime_metrics/` | Algoritmo compartilhado de extração; resultados ficam nos cenários |
| `tools/deploy/` | Compose básico |
| `tools/launcher/` | [Executor e testes](../tools/launcher/README.md) da entrada `./ariadne` |
| `tools/inspector/` | [Visualizador React com API local](../tools/inspector/README.md) dos resultados de cenários |
| `tools/inspector/scripts/` | [Exportação offline de fluxos e mídia](../tools/inspector/scripts/README.md) |
| `docs/` | Documentação pública atual |
| `internal-notes/` | Histórico interno de aprendizado; não é guia de uso |

Para acompanhar uma tarefa no código, leia nesta ordem: contrato,
[handler](../runtime/services/orchestrator/internal/server/server.go),
[executor](../runtime/services/orchestrator/internal/execution/executor.go),
[adaptador do agente](../sdk/python/src/ariadne_sdk/agent.py) e agente de domínio.
Para workflows, acrescente o [engine](../runtime/services/orchestrator/internal/workflow/engine.go).

## Preparar e verificar

Para desenvolver e verificar tudo a partir da raiz:

```sh
uv sync --project sdk/python --extra llm
make verify
```

A rotina cobre Go, SDK, integração real local, estudos, launcher, Inspector e
instalação mínima sem dependências LLM. Usa clientes falsos para LLM e Docker;
requer Go, uv e Node. `make test-go` mantém a verificação
isolada de Go. O [guia de consolidação](consolidation.md) descreve as opções.
Para alterações concorrentes do runtime, execute também `go test -race ./...`
dentro de `runtime/`.

## Escrever lógica de agente

Para autoria declarativa e execução gerenciada em processos locais, comece
por [experimentos em um arquivo](experiments.md). `Agent(handler=...)` e
`Agent.handle()` podem devolver um dicionário, que o SDK adapta ao contrato.
`start()`/`stop()` oferecem lifecycle explícito; `run()` permanece bloqueante.
O registro ocorre depois de iniciar o endpoint gRPC.

Para novos agentes, a API principal é `Agent.handle(task)`, com `Task` e
`TaskResult` do SDK. Exemplo de lógica local, sem iniciar serviços:

```python
from ariadne_sdk import Agent, Task, TaskResult


class GreetingAgent(Agent):
    capabilities = ["greeting"]

    def handle(self, task):
        return TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status="TASK_STATUS_COMPLETED",
            output={"greeting": f"Olá, {task.payload['name']}!"},
            trace=task.trace,
        )


agent = GreetingAgent.from_env()
result = agent.handle(Task(
    task_id="local-example",
    goal="Cumprimente a visitante",
    payload={"name": "Ana"},
))
assert result.output["greeting"] == "Olá, Ana!"
```

`from_env()` constrói a instância; `run()` inicia a integração com o runtime.
Para conectar um agente, configure Registry, host anunciado e porta conforme
a topologia. O endereço anunciado deve ser alcançável pelo Orchestrator:
`localhost` dentro de um contêiner aponta para esse próprio contêiner.

`execute_task()` com protobuf permanece como interface legada usada por alguns
exemplos. Para BDI, use `BdiAgent` com `Plan` (um ciclo, declarativo) ou com
`GoalPlan` (ciclo de deliberação com crenças por tarefa), sem subclasse; veja
[BDI declarativo, deliberativo e planejamento](bdi.md) e o
[agente de rotas](../studies/scenarios/routing/agents/route_planner/main.py).
Para LLM, prefira composição de `LlmCapability`, como no
[planejador e explicador](../studies/scenarios/routing/agents/planner_explainer/main.py); `mission_planning`
declara a capacidade de planejador de missão. Cada capacidade associa prompt,
modelo de resposta e conversão opcional; não exige subclasse.
`@llm_capability` continua disponível no SDK para agentes que precisem de métodos.

## Alterações no contrato

Os stubs gerados não devem ser editados manualmente. Antes de alterar o
`.proto`, classifique a compatibilidade, revise a versão, regenere os stubs
Go/Python e verifique consumidores, testes e checksum. O checksum detecta uma
alteração, mas não prova compatibilidade semântica.

`make proto` automatiza a geração; os includes são obtidos por
`pkg-config`, com fallback em `/usr/include`. Use `PROTO_INCLUDES=/caminho`
quando necessário. As ferramentas de geração são necessárias apenas para regenerar stubs.
O Makefile não executa cenários; para isso use o [executor ariadne](cli.md).

## Critério para uma mudança revisável

Descreva o comportamento alterado, atualize o guia público correspondente e
execute as verificações do componente afetado. Preserve os resultados
experimentais publicados: uma nova coleta deve ter identificação própria.
O comando `make verify` executa a rotina integrada também usada pelo CI em
`.github/workflows/verify.yml`, incluindo links locais da documentação e build
do frontend. O verificador de links confere destinos de links inline; não
consulta URLs externas nem valida âncoras.

O visualizador usa React, Vite e uma API FastAPI somente leitura. Instale as dependências com
`npm ci --prefix tools/inspector` e use Node 22 >=22.12 (linha do CI).
O intervalo aceito é `^20.19.0 || >=22.12.0`. Execute
`npm test --prefix tools/inspector` para o parser e
`npm run build --prefix tools/inspector` para validar a interface. Durante o
desenvolvimento, use `npm run api --prefix tools/inspector` e
`npm run dev --prefix tools/inspector` em terminais separados. Verifique a
listagem de execuções, navegação, busca e troca de fontes.

[Referência](reference.md) · [Índice](README.md)
