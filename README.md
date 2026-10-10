# TG Runtime — cooperação entre agentes heterogêneos

Implementação de referência de um trabalho de graduação sobre
**interoperabilidade entre agentes inteligentes**. O projeto define um contrato
comum para que agentes com arquiteturas diferentes sejam descobertos, recebam
tarefas, troquem mensagens e cooperem em workflows.

O runtime em Go coordena a execução e trata falhas. Os agentes Python mantêm
sua lógica de domínio: um agente LLM pode interpretar uma solicitação e um
agente BDI pode escolher um plano a partir de crenças e restrições.

```mermaid
flowchart LR
    C[Cliente] --> O[Orchestrator em Go]
    O --> R[Registry: descoberta e saúde]
    O --> L[Agente LLM em Python]
    O --> B[Agente BDI em Python]
    O --> E[Eventos e resultados]
```

A comunicação usa gRPC e Protocol Buffers. O contrato `contract.v1` está na
versão `1.0.0`; os stubs Go e Python estão incluídos no repositório.

## Escolha seu caminho

| Quero… | Comece aqui |
|---|---|
| Declarar agentes e cenário em um arquivo | [Experimentos declarativos](docs/experiments.md) |
| Experimentar sem chave de LLM | [Primeira execução](docs/quickstart.md) |
| Entender como funciona | [Arquitetura e conceitos](docs/architecture.md) |
| Explorar cooperação, falhas e mensagens | [Catálogo de cenários](docs/scenarios.md) |
| Desenvolver ou estender o projeto | [Guia de desenvolvimento](docs/development.md) |
| Avaliar o trabalho de graduação | [Guia de avaliação e evidências](docs/evaluation.md) |
| Apresentar o projeto ou explorar resultados | [Roteiro de apresentação](docs/presentation.md) e [visualizador local](tools/inspector/README.md) |

## Primeira experiência

Para explorar a nova interface de autoria, com **Go e uv** no host:

```sh
./tg run examples/echo.py
./tg run examples/workflow.py
```

Cada arquivo declara agentes e tarefas. O executor inicia o runtime Go e os
agentes em processos locais, salva logs e resultados e encerra os processos.
Veja o [guia de experimentos](docs/experiments.md), incluindo recuperação,
BDI e repetição com evidências brutas para avaliação separada.
A [API BDI declarativa](docs/bdi.md) permite definir agentes com `Input` e `Plan`,
sem subclasses, e oferece planejamento por busca genérica no SDK.

O [estudo logístico](studies/logistics/README.md) já usa essa interface:
`./tg run studies/logistics/experiment.py` executa BDI por padrão.
Depois, `./tg status` e `./tg logs` consultam a execução. LLM/híbrido,
campanhas e avaliação offline estão documentados no guia do estudo.

### Demonstração via Docker

Com Docker e Docker Compose >=2.24.4, a demonstração básica executa uma tarefa
`echo` pelo Registry, Orchestrator e agente mock, sem chave de LLM nem
instalação local de Go ou Python. A primeira preparação baixa dependências e
constrói imagens.

```sh
./tg doctor
./tg demo
```

O executor aguarda os agentes, salva resultados em `.tg/runs/` e encerra sua
topologia automaticamente. Use `./tg status` e `./tg logs` para inspecionar a
última execução. Veja todos os comandos em [referência do executor](docs/cli.md).

O [guia de primeira execução](docs/quickstart.md) reúne os comandos, a
verificação de prontidão, o resultado esperado e o encerramento do ambiente.
Depois, o [workflow sequencial](scenarios/workflow-sequential/README.md)
demonstra a coordenação de duas tarefas.

Para ler os resultados visualmente, inicie a API e a interface conforme o
[guia do visualizador](tools/inspector/README.md). A aplicação React lista as
execuções de `.tg/runs` e mostra tarefas, agentes e eventos. Inclui também um
exemplo registrado de recuperação que pode ser explorado sem Docker.

## O que está implementado

- Registro e descoberta por capacidade, heartbeat e detecção de falhas.
- Seleção de agentes, timeout por tentativa, retry e reassignment.
- Workflows com dependências, bindings de resultados, paralelismo e API assíncrona.
- Mensageria em memória entre agentes.
- SDK Python com `Agent`, `BdiAgent`, `LlmAgent` e `Scenario`.
- Cenários executáveis, benchmarks A–E e comparação logística BDI/LLM/híbrido.

É um protótipo de pesquisa para experimentos locais. Estado em memória,
mensageria sem reentrega e dependência do provedor LLM são limites relevantes;
veja [escopo e limitações](docs/limitations.md).

## Navegação

O [índice da documentação pública](docs/README.md) organiza os guias e a
referência técnica. O [mapa do código](docs/development.md#mapa-do-repositório)
indica os pontos de entrada da implementação. A licença é [Apache 2.0](LICENSE).
