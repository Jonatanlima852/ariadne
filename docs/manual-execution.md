# Execução manual do Compose básico

Este guia mantém o caminho manual para publicar portas no host e controlar
diretamente o Compose. Para começar, prefira [./ariadne demo](quickstart.md), com
prontidão e limpeza automáticas.

O exemplo envia uma tarefa `echo` a um agente descoberto pelo runtime.
Ele verifica a integração básica; a cooperação BDI/LLM é um cenário posterior.

## Requisitos

- Repositório clonado e terminal na sua raiz.
- Docker em execução, com Docker Compose v2.
- Portas locais 50051, 50052, 50053 e 60051 disponíveis.
- Rede para baixar imagens e dependências na primeira construção.

O caminho abaixo executa também o cliente no Docker. Não exige Go, Python,
`uv`, `protoc` ou credencial de LLM no host. Confira o Docker:

```sh
docker info
docker compose version
```

## 1. Iniciar e conferir a prontidão

```sh
docker compose -f tools/deploy/docker-compose.yml up --build -d
docker compose -f tools/deploy/docker-compose.yml ps
docker compose -f tools/deploy/docker-compose.yml logs --tail=50 registry orchestrator mock-agent
```

O Compose básico inicia Registry, Orchestrator, Messaging e mock-agent.
Ele ainda não tem healthchecks: `Up` indica que o contêiner está iniciado,
mas não garante que o agente já se registrou. Nos logs, aguarde as mensagens
de início dos serviços e `registered with registry` do mock-agent. Repita a
consulta de logs se necessário.

## 2. Enviar a tarefa

```sh
docker compose -f tools/deploy/docker-compose.yml --profile client run --build --rm client-runner \
  --goal "Teste ponta a ponta" --capability echo
```

Trecho esperado da resposta, com IDs e horário variáveis:

```text
Resultado:
  status   : COMPLETED
  agent_id : mock-agent-01
```

O cliente solicita a capacidade `echo`. O Orchestrator consulta o Registry,
escolhe um agente compatível e chama seu endpoint de execução. O resultado
retorna ao cliente com a identificação do agente.

O serviço Messaging também está disponível, mas esta tarefa usa chamadas
diretas ao agente e não publica um `MessageEnvelope`.

## 3. Observar e encerrar

```sh
docker compose -f tools/deploy/docker-compose.yml logs --tail=50 orchestrator mock-agent
docker compose -f tools/deploy/docker-compose.yml exec -T orchestrator cat /data/events.jsonl
docker compose -f tools/deploy/docker-compose.yml down
```

`down` remove os contêineres e a rede deste projeto, preservando o volume de
eventos. Assim, o JSONL pode conter execuções anteriores; use o `trace_id` da
resposta para identificar a tarefa atual. `down -v` também apaga o volume e
seu histórico; use essa variante apenas para uma limpeza deliberada.

## Diagnóstico

| Sintoma | O que conferir |
|---|---|
| Docker não responde | Inicie o Docker e repita `docker info` |
| Porta já ocupada | Encerre a outra topologia que usa a porta; os cenários de workflow e falha têm portas próprias |
| `UNAVAILABLE` | Confira `ps` e logs; aguarde os serviços e repita o envio |
| `no compatible agent found` | Confira o registro do mock-agent e a capacidade `echo` |
| Mock-agent encerrou ao iniciar | Com o Registry pronto, execute `docker compose -f tools/deploy/docker-compose.yml restart mock-agent` e confira o registro |
| Não há eventos no host | O Compose grava em `/data/events.jsonl`, no volume do contêiner |

## Cliente local, opcional

Com Python e `uv` disponíveis, mantendo o runtime iniciado:

```sh
uv run --project sdk/python python tools/clients/submit-task/main.py \
  --goal "Teste ponta a ponta" --capability echo
```

O cliente genérico atual serve ao caminho de tarefa simples. Para workflows,
use os scripts de cenário: eles interpretam `workflow_result`, que o cliente
genérico ainda não exibe corretamente.

## Próxima experiência

Execute o [workflow sequencial](../studies/scenarios/sequential_workflow/docker/README.md)
para observar duas tarefas coordenadas, ou escolha outro caso no
[catálogo de cenários](scenarios.md).

[Índice](README.md)
