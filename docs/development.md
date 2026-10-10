# Desenvolvimento

## Requisitos por atividade

| Atividade | Ferramentas |
|---|---|
| Demonstrações e cenários via `./tg` | Docker e Compose >=2.24.4 |
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
| `sdk/python/` | [API pública](../sdk/python/src/tg_sdk/__init__.py) e testes |
| `agents/` | Mock, echo, falha, rotas BDI, agendador BDI e LLM |
| `clients/submit-task/` | [Cliente de tarefa simples](../clients/submit-task/main.py) |
| `scenarios/` | Scripts de integração e topologias |
| `examples/` | Entradas didáticas e demo heterogênea |
| `studies/logistics/` | [Estudo declarativo](../studies/logistics/README.md), agentes, domínio, dataset e avaliação offline |
| `benchmarks/` | Campanhas, resultados selecionados e gráficos |
| `experiments/` | Extração de métricas e resultados locais |
| `infra/` | Compose básico |
| `scripts/launcher/` | [Executor e testes](../scripts/launcher/README.md) da entrada `./tg` |
| `tools/inspector/` | [Visualizador React com API local](../tools/inspector/README.md) dos resultados de cenários |
| `docs/` | Documentação pública atual |
| `internal-notes/` | Histórico interno de aprendizado; não é guia de uso |

Para acompanhar uma tarefa no código, leia nesta ordem: contrato,
[handler](../runtime/services/orchestrator/internal/server/server.go),
[executor](../runtime/services/orchestrator/internal/execution/executor.go),
[adaptador do agente](../sdk/python/src/tg_sdk/agent.py) e agente de domínio.
Para workflows, acrescente o [engine](../runtime/services/orchestrator/internal/workflow/engine.go).

## Preparar e verificar

Os comandos abaixo podem instalar dependências e gerar caches de desenvolvimento.
Parta da raiz. Para preparar o SDK:

```sh
uv sync --directory sdk/python
```

Para compilar e testar Go, em um subshell dentro do módulo:

```sh
(cd runtime && go build ./...)
(cd runtime && go test ./...)
```

As verificações Python estão separadas por responsabilidade:

```sh
uv run --directory sdk/python --with pytest python -m pytest tests -q
python3 -m unittest studies.logistics.test_domain
python3 -m unittest discover -s experiments/scripts -p 'test_*.py'
sh scripts/check-contract-freeze.sh
uv run --directory sdk/python python -m unittest discover -s ../../scripts/launcher -p 'test_*.py'
```

Os testes do SDK usam clientes falsos para LLM e não exigem chave. Integrações
reais são os [cenários](scenarios.md), executados separadamente.
`make test` roda apenas Go. Para alterações concorrentes no runtime, use também
`go test -race ./...` dentro de `runtime/`, em ambiente com suporte ao race detector.

## Escrever lógica de agente

Para autoria declarativa e execução gerenciada em processos locais, comece
por [experimentos em um arquivo](experiments.md). `Agent(handler=...)` e
`Agent.handle()` podem devolver um dicionário, que o SDK adapta ao contrato.
`start()`/`stop()` oferecem lifecycle explícito; `run()` permanece bloqueante.
O registro ocorre depois de iniciar o endpoint gRPC.

Para novos agentes, a API principal é `Agent.handle(task)`, com `Task` e
`TaskResult` do SDK. Exemplo de lógica local, sem iniciar serviços:

```python
from tg_sdk import Agent, Task, TaskResult


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
exemplos. Para BDI, consulte os métodos `@plan` do
[agente de rotas](../agents/bdi-agent/main.py). O custo é retornado no candidato
do plano; não é parâmetro do decorator. Para LLM, consulte os handlers
`@llm_capability` do [agente LLM](../agents/llm-agent/main.py): recebem objetivo e
contexto e retornam `Prompt`, com schema de saída declarado no decorator.

## Alterações no contrato

Os stubs gerados não devem ser editados manualmente. Antes de alterar o
`.proto`, classifique a compatibilidade, revise a versão, regenere os stubs
Go/Python e verifique consumidores, testes e checksum. O checksum detecta uma
alteração, mas não prova compatibilidade semântica.

`make proto` automatiza a geração; sua configuração atual de includes usa
Homebrew. Em outro ambiente, ajuste o caminho de includes ao protoc instalado.
Go e Homebrew são consultados apenas nas tarefas que precisam deles;
`make demo` e `make doctor` delegam ao [executor tg](cli.md).

## Critério para uma mudança revisável

Descreva o comportamento alterado, atualize o guia público correspondente e
execute as verificações do componente afetado. Preserve os resultados
experimentais publicados: uma nova coleta deve ter identificação própria.
O projeto ainda não tem pipeline de CI versionado nem um comando que execute
todas as verificações acima.

O visualizador usa React, Vite e uma API FastAPI somente leitura. Instale as dependências com
`npm install --prefix tools/inspector` e use Node >=18. Execute
`npm test --prefix tools/inspector` para o parser e
`npm run build --prefix tools/inspector` para validar a interface. Durante o
desenvolvimento, use `npm run api --prefix tools/inspector` e
`npm run dev --prefix tools/inspector` em terminais separados. Verifique a
listagem de execuções, navegação, busca e troca de fontes.

[Referência](reference.md) · [Índice](README.md)
