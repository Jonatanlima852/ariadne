# Estudo logístico

Este diretório reúne a descrição, os agentes, o domínio, os dados e a avaliação
offline. [scenario.py](scenario.py) declara os participantes e tarefas;
o SDK administra processos e o runtime Go executa o workflow.
[evaluate.py](evaluation/evaluate.py) analisa evidências depois, sem iniciar serviços.

## Mapa de leitura

| Pasta/entrada | O que ler aqui |
|---|---|
| `scenario.py` | Declaração do estudo original, agentes e tarefas |
| `domain/` | Simulação de referência e adaptação ao planejador do SDK |
| `datasets/` | Mundo, casos fixos e carregamento de dados |
| `agents/` | Interpretação LLM e planejamento BDI |
| `benchmarks/` | Coleta de campanhas e comparação histórica |
| `evaluation/` | Avaliação offline, métricas e relatórios |
| `docker/` | Topologia, cliente e adaptadores históricos |
| `tests/` | Testes de domínio e reprodução do estudo |

Comece por `scenario.py`, acompanhe os agentes em `agents/` e consulte
`domain/` para as regras. Para analisar uma coleta, siga para `evaluation/`.

## Executar um caso

Da raiz, com Go e uv:

```sh
ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py
./ariadne status
./ariadne logs
```

O padrão é híbrido (LLM interpreta e BDI planeja), no caso `avoid-contamination`.
Requer credencial e faz chamadas ao provedor. Mundo,
missão de referência, caso, estratégia e modelo ficam nos metadados do manifesto.
Esses metadados não são enviados automaticamente aos agentes: cada tarefa
recebe somente o payload declarado. Para escolher caso e estratégia:

```sh
LOGISTICS_CASE=impossible-deadline ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py
LOGISTICS_STRATEGY=hybrid ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py
LOGISTICS_STRATEGY=llm-only ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py
```

As estratégias com LLM exigem `OPENAI_API_KEY` exportada e acesso ao modelo
configurado por `LLM_MODEL`. O executor local não lê `.env` automaticamente.
LLM-only recebe pedido natural e mundo;
no híbrido, `interpret.output["mission"]` transfere a interpretação ao BDI.

O mundo, os oito casos, os prompts logísticos e as regras foram preservados.
Os consumidores Docker históricos reutilizam os agentes e domínio movidos;
os adaptadores antigos de cliente estão em [legacy_client.py](docker/legacy_client.py).

## Coletar uma campanha

Após a primeira execução preparar `.ariadne/bin`, colete os oito casos híbridos com
duas repetições:

```sh
uv run --project sdk/python --extra llm python -m studies.scenarios.logistics.benchmarks.campaign
```

Para comparar as duas estratégias, com chamadas LLM reais:

```sh
uv run --project sdk/python --extra llm python -m studies.scenarios.logistics.benchmarks.campaign \
  --strategies llm-only hybrid --repeat 2
```

A campanha intercala estratégias por caso e repetição. Salva `campaign.json`
e execuções em `.ariadne/campaigns/logistics-.../runs/`, com processos novos em cada
observação. `--cases` seleciona IDs, `--runtime-dir` escolhe binários e `--output`
escolhe a pasta de campanhas. Falhas e interrupções ficam registradas. Nenhuma
figura é gerada durante a coleta.

Essa política difere de `ariadne run --repeat N`, que reutiliza processos. Campanhas
têm seu próprio ponteiro de última execução; consulte uma observação pelo
caminho informado no terminal, por exemplo `./ariadne status CAMINHO/DA/EXECUCAO`.

## Avaliar as evidências

O avaliador usa somente a biblioteca padrão do Python:

```sh
python3 -m studies.scenarios.logistics.evaluation.evaluate .ariadne/runs/ariadne-ID
python3 -m studies.scenarios.logistics.evaluation.evaluate .ariadne/campaigns/logistics-ID
```

Substitua os IDs pelos caminhos reais. É possível fornecer várias entradas.
Uma pasta nova em `.ariadne/evaluations` recebe `logistics-results.json`,
`logistics-summary.csv` e `logistics-quality.svg`. `--output caminho-novo`
seleciona outro destino; um destino existente é rejeitado. Entradas não mudam.

A avaliação usa mundo e missão do manifesto. Erros de runtime e amostras
ausentes não contam como rejeições corretas de missões impossíveis.
Consistência exige duas observações do mesmo caso e mundo; uma observação
produz campo vazio no CSV e `N/A` no gráfico. Modelos distintos devem ser
avaliados separadamente por estratégia.

Campanhas interrompidas informam no JSON quantas observações estavam previstas
e quantas execuções foram registradas. Observações que nem chegaram a iniciar
não entram nas taxas; essa incompletude fica explicitada no relatório.

O BDI declara entradas e um plano em [mission_planner.py](agents/mission_planner.py), usando a busca genérica
do SDK por meio de [planning.py](domain/planning.py). O avaliador conserva sua busca
de referência em `domain/simulation.py`; as regras de domínio ainda são compartilhadas.
A otimalidade agregada inclui rejeições corretas. Preserve a revisão do avaliador para reproduzir
uma análise. Tokens nos resultados podem não incluir tentativas que falharam
antes de retornar metadados.

Todas as estratégias novas usam workflows. Suas latências não têm exatamente
o mesmo escopo das tarefas simples do benchmark histórico. Os resultados em
`studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2` preservam os conteúdos
da coleta histórica, antes localizada em `benchmarks/results/`. Os arquivos preservados incluem BDI-only da coleta antiga; os runners atuais
executam somente LLM-only e híbrido. A leitura das evidências antigas continua
disponível no avaliador, sem recolher BDI isolado.

## Verificar

```sh
uv run --project sdk/python --extra llm python -m unittest \
  studies.scenarios.logistics.tests.test_domain studies.scenarios.logistics.tests.test_study -q
```

Com `ARIADNE_TEST_RUNTIME_DIR="$PWD/.ariadne/bin"`, inclui integração híbrida com Go real
e cliente LLM falso, identificado como `test-only`. Esse teste não é resultado
experimental de uma LLM real.

[Avaliação do TCC](../../../docs/evaluation.md) · [Interface declarativa](../../../docs/experiments.md)

A coleta usa `ariadne_sdk.campaign`, compartilhado com outros estudos. Execuções
registram revisão, pacotes e hashes de mundo/casos; a avaliação registra seu
código e hashes das evidências. Veja [proveniência](../../../docs/consolidation.md).

Os contêineres usam os mesmos agentes locais: `mission-planner` e
`mission-assistant`. Não dependem dos agentes de rotas. A configuração
operacional fica em [agents/serve.py](agents/serve.py).
