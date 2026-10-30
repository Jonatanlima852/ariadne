# Referência do executor `ariadne`

`./ariadne` é um bootstrap shell para a CLI Python, também instalada como
`ariadne`. No checkout, uv prepara o SDK; `ARIADNE_PYTHON` seleciona um ambiente
já instalado e `ARIADNE_SDK_EXTRAS=llm` inclui o extra LLM. Toda execução usa
Docker Compose >=2.24.4: não há backend de processos locais nem topologias
escritas à mão.

## Comandos

| Comando | Comportamento |
|---|---|
| `./ariadne run ARQUIVO.py` | Constrói as imagens se necessário, sobe serviços e agentes em contêineres, aplica o cenário e remove tudo |
| `./ariadne check ARQUIVO.py` | Valida a descrição sem iniciar contêineres |
| `./ariadne campaign ARQUIVO.py` | Coleta uma matriz de execuções independentes, uma topologia por observação, em `campaigns/` ao lado do cenário |
| `./ariadne status [ID]` | Estado salvo e localização dos resultados |
| `./ariadne logs [ID]` | Logs salvos de serviços e agentes |
| `./ariadne stop [ID]` | Remove contêineres que uma interrupção abrupta tenha deixado |
| `./ariadne doctor [--file ARQUIVO.py] [--llm]` | Confere Python, SDK, Docker, Compose, destino e, opcionalmente, descrição e extra LLM |
| `./ariadne viewer [--root DIR] [--port N] [--no-browser]` | Abre o Mission Viewer com as missões de `.ariadne` e dos estudos |
| `./ariadne verify` | Verificação integrada do checkout; use o extra `llm` |
| `./ariadne help` | Ajuda |

Opções de `run`: `--repeat N` repete o cenário na mesma topologia, preservando
cada amostra; `--timeout S` limita o RPC de cada amostra (60 s); `--ready-timeout S`
limita cada espera de prontidão (60 s); `--output DIR` muda a pasta de evidências
(veja [Pasta de uma execução](#pasta-de-uma-execução)). O ID padrão de `status`,
`logs` e `stop` é o da última execução iniciada neste checkout.

## O que `run` faz

1. Carrega o `scenario.py`, valida a declaração e registra proveniência.
2. Gera `compose.yaml` na pasta da execução: `registry`, `orchestrator` e
   `messaging` a partir dos Dockerfiles de `runtime/services/`, e um serviço
   `agent-N` por agente, todos com a imagem genérica de
   [sdk/python/Dockerfile](../sdk/python/Dockerfile).
3. Monta o repositório (somente leitura) e a pasta da execução nos contêineres,
   nos mesmos caminhos do host. Cada `agent-N` executa `ariadne_sdk.worker`
   com o arquivo e o índice do agente; o agente anuncia `agent-N:60051`.
4. Publica as portas dos serviços em `127.0.0.1` com portas efêmeras; o
   cliente da amostra roda no host contra o Orchestrator publicado.
5. Ao final, salva o log de cada contêiner e executa `docker compose down`.

Cada execução tem projeto Compose próprio (o ID da execução), então execuções
simultâneas não colidem. As imagens `ariadne-registry:local`,
`ariadne-orchestrator:local`, `ariadne-messaging:local` e `ariadne-agent:local`
ficam como cache; mudanças em `runtime/` ou nas dependências do SDK são
reconstruídas na próxima execução, mudanças em código Python não exigem rebuild.

## Variáveis de ambiente

O executor não lê `.env`. As variáveis que a descrição consultou ao ser
carregada (por exemplo `FANOUT_WORKERS`, `LOGISTICS_V3_CASE`, `ROUTING_DEMO`)
e as credenciais `OPENAI_API_KEY`, `OPENAI_BASE_URL` e `LLM_MODEL` são
repassadas por nome aos contêineres de agente quando existirem no terminal.
Os valores não são escritos no `compose.yaml` nem nas evidências; o manifesto
lista apenas os nomes em `forwarded_environment`.

```sh
export OPENAI_API_KEY=...
./ariadne run studies/scenarios/routing/scenario.py
```

## Pasta de uma execução

Por padrão, um cenário do repositório grava em `runs/` ao lado do seu
`scenario.py` (por exemplo `studies/scenarios/fanout/runs/ariadne-<id>/`);
um arquivo fora de `studies/scenarios/` grava em `.ariadne/runs/`. `--output`
muda a pasta e `ARIADNE_RUNS_DIR` define outro padrão. As pastas `runs/` são
ignoradas pelo Git; coletas que valem a pena preservar são copiadas para
`results/<data>/` do cenário, com um README.

```
ariadne-<id>/
  manifest.json        declaração compilada, agentes e serviços, imagens, endereços publicados, proveniência
  summary.json         cenário, estado (RUNNING/COMPLETED/FAILED/CANCELLED), ambiente, duração, erro
  result.json          resposta da última amostra
  results.jsonl        uma linha por amostra, inclusive falhas de RPC
  mission-result.json  MissionResult do contrato, só em missões; o Viewer lê este e o manifest.json
  events.jsonl         eventos do Orchestrator (tarefas, workflows, timeouts, reatribuições)
  logs/
    compose.yaml, compose.log       topologia gerada e saída dos comandos Compose
    execution.jsonl                 ciclo do executor, comandos Compose e amostras
    experiment.py                   cópia da descrição executada
    registry.log, orchestrator.log, messaging.log, message-events.jsonl
    agent-N.log, agent-N.jsonl      log do contêiner e entrada/resultado de cada tentativa do agente N
```

`./ariadne status` e `./ariadne logs` sem argumento abrem a última execução,
registrada em `.ariadne/latest`; com um ID, procuram em `.ariadne/runs` e nos
`runs/` de todos os cenários; um caminho também é aceito.

## Make e `./ariadne`

Os dois têm papéis distintos. O Makefile cobre construção e verificação do
código (`proto`, `contract-check`, `build`, `verify`, `test-go`). Tudo que
executa ou observa o sistema passa por `./ariadne`.

[Primeira execução](quickstart.md) · [Experimentos](experiments.md) · [Índice](README.md)
