# Referência do executor `tg`

`./tg run arquivo.py` e `./tg check arquivo.py` oferecem o novo caminho de
[experimentos declarativos](experiments.md), com Go e uv. A referência abaixo
descreve principalmente o launcher Docker. `status` e `logs` reconhecem também
execuções locais, por ID ou caminho, sem exigir Docker ou uv para ler os arquivos.
O ponteiro de última execução é compartilhado. Para processos locais, `logs`
mostra até 100 linhas por arquivo; `stop` ainda se aplica somente a Docker.

`tg` é um script shell na raiz do repositório. Localiza os arquivos a partir
de seu próprio diretório e pode ser chamado por caminho absoluto. Reutiliza
topologias e scripts de cenários, executando o cliente Python em contêiner.
Docker e Compose >=2.24.4 são os requisitos.

## Comandos

| Comando | Comportamento |
|---|---|
| `./tg help` | Ajuda, sem exigir Docker |
| `./tg doctor [cenário]` | Verifica ferramentas e configuração; padrão `demo` |
| `./tg demo [--keep]` | Tarefa simples, com conclusão verificada |
| `./tg scenario` | Lista os cenários disponíveis |
| `./tg scenario NOME [--keep]` | Executa e valida um cenário |
| `./tg status [ID]` | Estado salvo e localização dos resultados |
| `./tg logs [ID]` | Logs exportados e, se o ambiente estiver ativo, logs atuais |
| `./tg stop [ID]` | Exporta dados e encerra somente essa execução |

O ID padrão é o da última execução iniciada neste checkout. Em execuções
simultâneas, use o ID explícito. `stop` pode ser repetido após um encerramento
bem-sucedido. `status` exibe o estado registrado pelo executor; não é um
monitor contínuo de saúde do Docker.

## Isolamento e limpeza

Cada execução recebe um projeto Compose e volume exclusivos, com dados em
`.tg/runs/ID/`. Overrides removem as portas publicadas; o cliente acessa os
serviços pela rede Docker. Os comandos Compose manuais mantêm seus projetos
e portas originais.

O executor aguarda canais gRPC e consulta o Registry até encontrar os agentes
esperados com capacidade correta, estado ALIVE/BUSY e endpoint acessível.

Sem `--keep`, contêineres e rede são encerrados ao final. Eventos são copiados
antes de remover o volume. Se a exportação falhar, o volume é preservado e seu
nome é informado para recuperação; os demais recursos ainda são encerrados.
As imagens construídas permanecem como cache local.

Ctrl+C e SIGTERM acionam a limpeza. Uma interrupção abrupta do host/processo
pode impedir esse tratamento; `./tg stop ID` retoma o encerramento. O comando
usa uma descrição de controle sem credenciais, inclusive para parar um
cenário LLM depois de remover seu `.env`.

## Arquivos de uma execução

| Arquivo | Conteúdo |
|---|---|
| `status`, `environment`, `scenario` | Estado operacional salvo e cenário escolhido |
| `build.log`, `startup.log` | Construção e inicialização |
| `runner.log` | Prontidão e resumo da validação |
| `scenario.log` | Saída detalhada do script de cenário |
| `summary.json` | Estado, duração incluindo prontidão e eventual erro |
| `result.json` | Resultado estruturado do domínio, workflow ou mensagem |
| `result.evaluation.json` | Avaliação adicional do cenário logístico |
| `services.log` | Logs dos serviços exportados antes da limpeza |
| `events.jsonl` ou `message-events.jsonl` | Eventos do Orchestrator ou broker desta execução |
| `diagnostics.log`, `cleanup.log` | Diagnóstico e encerramento |

Uma falha anterior ao cenário pode impedir a criação de `summary.json` e
`result.json`; consulte `status` e os logs da etapa que falhou. `.tg/` é
ignorado pelo Git e excluído do contexto de build. Esses relatórios
operacionais não substituem a metodologia dos benchmarks.

Esses arquivos podem ser abertos no [visualizador local](../tools/inspector/README.md).
A API local somente leitura fornece as evidências ao frontend e não depende de
os serviços ainda estarem ativos.

## Prazos

```sh
TG_READY_TIMEOUT=120 TG_SCENARIO_TIMEOUT=300 ./tg scenario heterogeneous-route
```

Os valores são segundos inteiros entre 1 e 3600. Prontidão usa 90 segundos
por padrão; cenário usa 180. O build não entra nesses prazos. O timeout
externo não altera retry, deadlines ou timeout de workflow dentro do runtime.

## Cenários com LLM

`heterogeneous-route` e `logistics-mission` fazem chamadas reais e podem gerar
custo no provedor. O arquivo de ambiente é escolhido nesta ordem:

1. `TG_ENV_FILE`, se informado (caminho relativo à raiz ou absoluto).
2. `scenarios/heterogeneous-route/.env`, apenas para o cenário de rota, se existir.
3. `.env` na raiz, se existir.

Também é possível fornecer `OPENAI_API_KEY` e `LLM_MODEL` pelo ambiente do
processo; variáveis exportadas têm precedência na interpolação Compose.
`OPENAI_API_KEY` é obrigatória; `LLM_MODEL` é opcional. O default atual do
projeto é `gpt-5.6-luna`, sujeito ao acesso da conta.

```sh
./tg doctor heterogeneous-route
./tg scenario heterogeneous-route
./tg scenario logistics-mission
```

`doctor` valida configuração, mas não testa credencial nem acesso ao modelo.
Cenários determinísticos não carregam `.env` pelo executor e não chamam LLM.

## Make e execução manual

`make demo` e `make doctor` delegam para `./tg`. `make up`, `make logs` e
`make down` continuam controlando o Compose básico manual, não execuções de
`./tg`. Para estas, use `./tg logs` e `./tg stop`.

Os scripts `benchmarks/run.sh` e `benchmarks/run-logistics.sh` continuam sendo
os executores das campanhas. `tg` cobre demonstrações e cenários; não oferece
um subcomando de benchmark nesta versão.

[Primeira execução](quickstart.md) · [Índice](README.md)
