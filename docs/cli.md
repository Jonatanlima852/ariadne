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
| `./ariadne campaign ARQUIVO.py` | Coleta uma matriz de execuções independentes, uma topologia por observação |
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
(`ARIADNE_RUNS_DIR`, padrão `.ariadne/runs`). O ID padrão de `status`, `logs` e
`stop` é o da última execução iniciada neste checkout.

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

## Arquivos de uma execução

| Arquivo | Conteúdo |
|---|---|
| `manifest.json` | Descrição compilada, agentes e serviços, imagens, endereços publicados, proveniência |
| `compose.yaml`, `compose.log` | Topologia gerada e saída dos comandos Compose |
| `experiment.py` | Cópia da descrição executada |
| `execution.jsonl` | Ciclo do executor, comandos Compose e amostras |
| `events.jsonl`, `message-events.jsonl` | Eventos do Orchestrator e do broker |
| `agent-N.jsonl` | Entrada e resultado de cada tentativa recebida pelo agente N |
| `registry.log`, `orchestrator.log`, `messaging.log`, `agent-N.log` | Log de cada contêiner |
| `results.jsonl`, `result.json` | Uma resposta por amostra e a última amostra |
| `mission-result.json` | `MissionResult` do contrato, quando o cenário é uma missão |
| `summary.json`, `status`, `environment`, `backend` | Estado e duração operacional |

`.ariadne/` é ignorado pelo Git e excluído do contexto de build.

## Make e `./ariadne`

Os dois têm papéis distintos. O Makefile cobre construção e verificação do
código (`proto`, `contract-check`, `build`, `verify`, `test-go`). Tudo que
executa ou observa o sistema passa por `./ariadne`.

[Primeira execução](quickstart.md) · [Experimentos](experiments.md) · [Índice](README.md)
