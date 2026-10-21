# Ariadne

**Framework para execução e cooperação de agentes heterogêneos.**

Desenvolvido como implementação de referência de um trabalho de graduação sobre
**interoperabilidade entre agentes inteligentes**, Ariadne define um contrato
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

O caminho recomendado usa **Go e uv**, sem Docker nem chave de LLM:

```sh
./ariadne doctor --local --file studies/scenarios/basic_task/scenario.py
./ariadne run studies/scenarios/basic_task/scenario.py
./ariadne status
```

Siga o [guia de primeira execução](docs/quickstart.md) para preparar o ambiente,
reconhecer a resposta esperada e abrir o resultado no Inspector. O executor
inicia os serviços e agentes, salva evidências e encerra seus processos.

Depois, explore [workflows e recuperação](docs/experiments.md),
[BDI declarativo](docs/bdi.md) e o [estudo logístico](studies/scenarios/logistics/README.md).
Abra `./ariadne inspect` para explorar amostras, campanhas, avaliações e
demonstrações registradas, com grafo e replay manual dos eventos.

Como alternativa, com **uv e Docker Compose >=2.24.4**, use `./ariadne doctor`
e `./ariadne demo`. O uv prepara o Python da CLI; Go não é necessário no host.
Veja o [caminho Docker](docs/quickstart.md#alternativa-com-docker).

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

## Organização e verificação

O núcleo está em `proto/`, `runtime/` e `sdk/`. [`studies/`](studies/README.md) reúne todos os cenários, seus agentes e avaliações; `tools/` contém o suporte
operacional. Veja [organização, autoria e reprodução](docs/consolidation.md).

`make verify` executa as verificações de Go, Python, integração e ferramentas,
sem chamadas LLM reais. A mesma rotina é executada pelo CI.
