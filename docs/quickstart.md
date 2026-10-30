# Primeira execução

Tudo roda em contêineres: `./ariadne run` sobe Registry, Orchestrator e
Messaging mais um contêiner por agente declarado, aplica o cenário e derruba
tudo ao final. Não exige Go, protoc nem chave de LLM no host. Execute os
comandos na raiz do repositório.

## 1. Preparar e conferir

Instale Docker com Compose v2 (>=2.24.4) e uv. Use macOS/Linux ou WSL. O uv
prepara o Python da CLI; a primeira execução pode baixar dependências.

```sh
./ariadne doctor --file studies/scenarios/basic_task/scenario.py
```

Todas as linhas devem começar com `OK`. O diagnóstico confere Python, SDK,
Docker, Compose, destino de evidências e a descrição do exemplo. Não constrói
imagens nem inicia contêineres.

## 2. Executar

```sh
./ariadne run studies/scenarios/basic_task/scenario.py
```

Na primeira vez o executor constrói quatro imagens: três serviços Go e uma
imagem genérica de agente Python. Depois disso, cada execução leva poucos
segundos. O terminal deve mostrar:

```text
Amostra 1/1: WORKFLOW_STATUS_COMPLETED
Resultado: {"text": "Olá, Ariadne!"}
Estado: COMPLETED
Evidências: .../.ariadne/runs/ariadne-.../
```

A tarefa pede a capacidade `echo`; o runtime descobre o agente e recebe sua
resposta. `COMPLETED` indica conclusão operacional, não uma avaliação científica.

## 3. Consultar o resultado

```sh
./ariadne status
./ariadne logs
```

Sem argumento, consultam a última execução. `result.json` contém a resposta;
`events.jsonl` registra os eventos do Orchestrator; `manifest.json` descreve o
experimento, as imagens e os endereços publicados; `compose.yaml` é a
topologia gerada. Os logs de cada contêiner ficam em `registry.log`,
`orchestrator.log`, `messaging.log` e `agent-N.log`. Para interromper uma
execução, use Ctrl+C: os contêineres são removidos e as evidências ficam.

## 4. Explorar cooperação, recuperação e missões

```sh
./ariadne run studies/scenarios/sequential_workflow/scenario.py
./ariadne run studies/scenarios/failure_reassignment/scenario.py
./ariadne run studies/scenarios/messaging/scenario.py
ROUTING_DEMO=1 ./ariadne run studies/scenarios/routing/scenario.py
./ariadne run studies/scenarios/fanout/scenario.py
```

O primeiro transfere a saída entre etapas; o segundo mostra timeout e
reassignment; o terceiro troca um envelope pelo serviço de mensagens; os dois
últimos são missões do contrato 2.0.0, com planejador, passos paralelos e
reatribuição. Nenhum deles chama LLM. Consulte [experimentos](experiments.md)
e o [catálogo de cenários](scenarios.md).

## 5. Abrir a visualização

`./ariadne viewer` abre o [Mission Viewer](../tools/mission-viewer/README.md) com as
missões de `.ariadne/runs`: grafo de dependências por rodada, linha do tempo por
agente e, ao clicar num bloco, a entrada e a saída daquela chamada. Cenários de
workflow (eco, workflow sequencial, falha) são lidos nos arquivos `result.json`
e `events.jsonl` da execução.

## Diagnóstico rápido

| Situação | Próximo passo |
|---|---|
| uv ausente | Instale uv ou configure `ARIADNE_PYTHON` com um Python que tenha o SDK |
| Docker indisponível | Inicie o Docker e repita `./ariadne doctor` |
| Falha ao construir imagens | Leia `compose.log` na pasta informada; confira rede e espaço em disco |
| Contêiner não ficou pronto | `./ariadne logs` mostra o log de cada serviço e agente |
| Contêineres sobraram após uma interrupção abrupta | `./ariadne stop ID` remove o projeto Compose da execução |

[Índice](README.md)
