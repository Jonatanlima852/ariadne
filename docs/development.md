# Desenvolvimento

## Requisitos por atividade

| Atividade | Ferramentas |
|---|---|
| Executar cenários e campanhas (`./ariadne run`) | uv e Docker com Compose >=2.24.4 |
| SDK, análises e testes unitários Python | uv e Python compatível com o projeto |
| Testar o runtime Go fora dos contêineres | Go 1.26.3 ou compatível com `runtime/go.mod` |
| Regenerar contrato | Go, protoc, plugins Go, uv e grpcio-tools |

Os projetos Python declaram Python >=3.11. O SDK possui `.python-version` com
3.14; uv pode selecionar ou baixar esse interpretador. A imagem genérica de
agente usa Python 3.12. Consulte [pyproject.toml](../sdk/python/pyproject.toml),
[.python-version](../sdk/python/.python-version) e [go.mod](../runtime/go.mod).

## Mapa do repositório

| Diretório | Conteúdo e ponto de entrada |
|---|---|
| `proto/` | [Contrato](../proto/contract/v1/contract.proto), versão e checksum |
| `runtime/` | Módulo Go, serviços e stubs gerados |
| `sdk/python/` | [API pública](../sdk/python/src/ariadne_sdk/__init__.py), [executor em contêineres](../sdk/python/src/ariadne_sdk/compose.py), [imagem do agente](../sdk/python/Dockerfile) e testes |
| `runtime/services/*/Dockerfile` | Imagens dos três serviços Go |
| `studies/scenarios/*/agents/` | Echo, falha, rotas BDI, agendador BDI e LLM |
| `studies/scenarios/` | Cenários, regras, dados e avaliações próprios |
| `studies/scenarios/logistics/` | [Estudo logístico](../studies/scenarios/logistics/README.md): v3 corrente e v2 histórica |
| `studies/scenarios/logistics/v2/` | [Episódios com múltiplos pedidos](../studies/scenarios/logistics/v2/README.md), agentes especialistas e evidências preservadas |
| `studies/scenarios/*/campaign.py`, `analysis.py` | Matriz de execuções para `./ariadne campaign` e análise das evidências, quando o cenário tem |
| `studies/scenarios/*/results/` | Coletas preservadas, com README por data |
| `tools/runtime_metrics/` | Algoritmo compartilhado de extração; resultados ficam nos cenários |
| `tools/mission-viewer/` | [Mission Viewer](../tools/mission-viewer/README.md) das missões do contrato 2.0.0 |
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

A rotina cobre contrato, links da documentação, Go, SDK, integrações reais em
contêineres, estudos, métricas e a instalação mínima do SDK sem OpenAI/Pydantic.
Usa clientes falsos para LLM; requer Docker, Go e uv. `--unit-only` omite as
integrações em contêineres. `make test-go` mantém a verificação isolada de Go; para
alterações concorrentes do runtime, execute também `go test -race ./...`
dentro de `runtime/`. A mesma rotina está em
[.github/workflows/verify.yml](../.github/workflows/verify.yml).

### Bootstrap e nomes

`./ariadne` é um bootstrap curto para a CLI Python instalada como `ariadne`;
parsing, validação, execução e geração do Compose estão no SDK
(`ariadne_sdk/__main__.py`, `execution.py`, `compose.py`). `run` e `verify`
precisam do checkout, porque as imagens são construídas a partir dele;
configure `ARIADNE_ROOT` quando necessário. `ARIADNE_PYTHON` usa um Python
com o SDK já instalado em vez do uv; `ARIADNE_SDK_EXTRAS=llm` inclui o extra.
`check` detecta limite de etapas e profundidade, políticas desconhecidas e
parâmetros de retry inválidos antes de iniciar contêineres; o Go continua
sendo a validação definitiva.

O pacote é `ariadne-sdk`, os imports usam `ariadne_sdk`, as variáveis
operacionais usam `ARIADNE_*` e as evidências ficam em `.ariadne/`. O módulo
Go é `ariadne/runtime`; as imagens são `ariadne-registry`,
`ariadne-orchestrator`, `ariadne-messaging` e `ariadne-agent`. Evidências
anteriores à renomeação conservam seus caminhos; `./ariadne status` e
`./ariadne logs` aceitam o caminho de uma execução antiga.

## Escrever lógica de agente

Para autoria declarativa e execução gerenciada em contêineres, comece
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
Dentro de `./ariadne run`, o executor define Registry, host anunciado
(`agent-N`) e porta de cada contêiner; o agente não precisa dessa configuração.

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

O [Mission Viewer](../tools/mission-viewer/README.md) é uma página estática
sem dependências: `tools/mission-viewer/index.html` e um servidor de índice em
`serve.py`, só biblioteca padrão. Para mudar o desenho, edite o HTML e abra
com `./ariadne viewer`.

[Referência](reference.md) · [Índice](README.md)
