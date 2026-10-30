# Referência do executor `ariadne`

`./ariadne run arquivo.py` e `./ariadne check arquivo.py` oferecem o novo caminho de
[experimentos declarativos](experiments.md), com Go e uv. A referência abaixo
descreve principalmente o launcher Docker. `status` e `logs` reconhecem também
execuções locais, por ID ou caminho, sem exigir Docker. A CLI usa Python com
o SDK; o bootstrap pode preparar esse ambiente pelo uv.
O ponteiro de última execução é compartilhado. Para processos locais, `logs`
mostra até 100 linhas por arquivo; `stop` ainda se aplica somente a Docker.

`./ariadne` é um bootstrap shell para a CLI Python, também instalada como `ariadne`.
Os mesmos argumentos e comportamentos valem nas duas entradas. No checkout,
uv prepara o SDK; `ARIADNE_PYTHON` seleciona um ambiente já instalado. Os comandos
Docker exigem adicionalmente Docker Compose >=2.24.4 e usam o backend de
`tools/launcher/`, com o cliente da tarefa em contêiner.

## Comandos

| Comando | Comportamento |
|---|---|
| `./ariadne inspect` | Inicia API e frontend do Inspector; Ctrl+C encerra ambos |
| `./ariadne help` | Ajuda, sem exigir Docker |
| `./ariadne run ARQUIVO.py` | Executa uma descrição local |
| `./ariadne check ARQUIVO.py` | Valida entradas e limites estáticos |
| `./ariadne campaign ARQUIVO.py` | Coleta uma matriz com execuções independentes |
| `./ariadne verify` | Verificação integrada; use o extra `llm` |
| `./ariadne doctor --local [--file ARQUIVO.py]` | Confere Python, SDK, Go/binários, destino e descrição opcional |
| `./ariadne doctor [cenário]` | Verifica ferramentas e configuração; padrão `demo` |
| `./ariadne demo [--keep]` | Tarefa simples, com conclusão verificada |
| `./ariadne scenario` | Lista os cenários disponíveis |
| `./ariadne scenario NOME [--keep]` | Executa e valida um cenário |
| `./ariadne status [ID]` | Estado salvo e localização dos resultados |
| `./ariadne logs [ID]` | Logs exportados e, se o ambiente estiver ativo, logs atuais |
| `./ariadne stop [ID]` | Exporta dados e encerra somente essa execução |

O ID padrão é o da última execução iniciada neste checkout. Em execuções
simultâneas, use o ID explícito. `stop` pode ser repetido após um encerramento
bem-sucedido. `status` exibe o estado registrado pelo executor; não é um
monitor contínuo de saúde do Docker.

## Isolamento e limpeza

Cada execução recebe um projeto Compose e volume exclusivos, com dados em
`.ariadne/runs/ID/`. Overrides removem as portas publicadas; o cliente acessa os
serviços pela rede Docker. Os comandos Compose manuais mantêm seus projetos
e portas originais.

O executor aguarda canais gRPC e consulta o Registry até encontrar os agentes
esperados com capacidade correta, estado ALIVE/BUSY e endpoint acessível.

Sem `--keep`, contêineres e rede são encerrados ao final. Eventos são copiados
antes de remover o volume. Se a exportação falhar, o volume é preservado e seu
nome é informado para recuperação; os demais recursos ainda são encerrados.
As imagens construídas permanecem como cache local.

Ctrl+C e SIGTERM acionam a limpeza. Uma interrupção abrupta do host/processo
pode impedir esse tratamento; `./ariadne stop ID` retoma o encerramento. O comando
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
`result.json`; consulte `status` e os logs da etapa que falhou. `.ariadne/` é
ignorado pelo Git e excluído do contexto de build. Esses relatórios
operacionais não substituem a metodologia dos benchmarks.

Esses arquivos podem ser abertos no [visualizador local](../tools/inspector/README.md).
A API local somente leitura fornece as evidências ao frontend e não depende de
os serviços ainda estarem ativos.

## Prazos

```sh
ARIADNE_READY_TIMEOUT=120 ARIADNE_SCENARIO_TIMEOUT=300 ./ariadne scenario heterogeneous-route
```

Os valores são segundos inteiros entre 1 e 3600. Prontidão usa 90 segundos
por padrão; cenário usa 180. O build não entra nesses prazos. O timeout
externo não altera retry, deadlines ou timeout de workflow dentro do runtime.

## Cenários com LLM

`heterogeneous-route` e `logistics-mission` fazem chamadas reais e podem gerar
custo no provedor. O arquivo de ambiente é escolhido nesta ordem:

1. `ARIADNE_ENV_FILE`, se informado (caminho relativo à raiz ou absoluto).
2. `studies/scenarios/routing/docker/.env`, apenas para o cenário de rota, se existir.
3. `.env` na raiz, se existir.

Também é possível fornecer `OPENAI_API_KEY` e `LLM_MODEL` pelo ambiente do
processo; variáveis exportadas têm precedência na interpolação Compose.
`OPENAI_API_KEY` é obrigatória; `LLM_MODEL` é opcional. O default atual do
projeto é `gpt-5.6-luna`, sujeito ao acesso da conta.

```sh
./ariadne doctor heterogeneous-route
./ariadne scenario heterogeneous-route
./ariadne scenario logistics-mission
```

`doctor` valida configuração, mas não testa credencial nem acesso ao modelo.
Cenários determinísticos não carregam `.env` pelo executor e não chamam LLM.

## Make e `./ariadne`

Os dois têm papéis distintos. O Makefile cobre construção e verificação do
código (`proto`, `contract-check`, `build`, `verify`, `test-go`). Tudo que
executa ou observa o sistema passa por `./ariadne`: cenários, campanhas,
`status`, `logs` e `stop`. Nenhum comando existe nos dois.

Os scripts `studies/scenarios/<assunto>/benchmarks/run.sh` continuam sendo
os executores das campanhas. `ariadne` cobre demonstrações e cenários; não oferece
um subcomando de benchmark nesta versão.

[Primeira execução](quickstart.md) · [Índice](README.md)

Veja [organização e reprodução](consolidation.md) para dependências opcionais,
`Campaign`, proveniência e detalhes da implementação única da CLI.

## Diagnóstico local

`./ariadne doctor --local` verifica o ambiente do executor local. Use `--file`
para validar também o experimento, `--llm` para conferir dependências opcionais
e presença de `OPENAI_API_KEY`, e `--inspector` para conferir Node, npm e uv.
A chave nunca é exibida e não há chamada ao provedor.

`--runtime-dir` confere os três binários executáveis e dispensa Go; alternativamente,
`--runtime-source` confere a versão Go exigida pelo módulo. As variáveis
`ARIADNE_RUNTIME_DIR` e `ARIADNE_RUNTIME_SOURCE` também são reconhecidas.
`--output` seleciona o destino cuja permissão de escrita será conferida.
Essas opções exigem `--local` e não podem ser combinadas com cenário Docker.

O diagnóstico retorna código 1 se alguma checagem falhar. Não instala, compila
ou inicia serviços, mas o bootstrap uv pode preparar o SDK antes de executá-lo.
Como `check`, `--file` importa o arquivo Python: mantenha o topo declarativo.
A verificação não garante acesso à rede/modelo ou prontidão futura dos serviços.

## Abrir o Inspector

`./ariadne inspect` inicia o visualizador em localhost:4173 e sua API em 8787.
Requer checkout, uv, npm e Node compatível com o frontend; prepara dependências
quando necessário. Use `--port`, `--api-port` e `--ready-timeout` para configurar
portas e espera de prontidão. `--runs-dir`, `--campaigns-dir` e `--evaluations-dir`
selecionam diretórios de evidências. Ctrl+C encerra os processos supervisionados.
Veja [o guia do Inspector](../tools/inspector/README.md).
