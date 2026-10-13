# Estudo logístico

Este diretório reúne a descrição, os agentes, o domínio, os dados e a avaliação
offline. [experiment.py](experiment.py) declara os participantes e tarefas;
o SDK administra processos e o runtime Go executa o workflow.
[evaluate.py](evaluate.py) analisa evidências depois, sem iniciar serviços.

## Executar um caso

Da raiz, com Go e uv:

```sh
./tg run studies/logistics/experiment.py
./tg status
./tg logs
```

O padrão usa BDI e `avoid-contamination`, sem chave ou chamada LLM. Mundo,
missão de referência, caso, estratégia e modelo ficam nos metadados do manifesto.
Esses metadados não são enviados automaticamente aos agentes: cada tarefa
recebe somente o payload declarado. Para escolher caso e estratégia:

```sh
LOGISTICS_CASE=impossible-deadline ./tg run studies/logistics/experiment.py
TG_SDK_EXTRAS=llm LOGISTICS_STRATEGY=hybrid ./tg run studies/logistics/experiment.py
TG_SDK_EXTRAS=llm LOGISTICS_STRATEGY=llm-only ./tg run studies/logistics/experiment.py
```

As estratégias com LLM exigem `OPENAI_API_KEY` exportada e acesso ao modelo
configurado por `LLM_MODEL`. O executor local não lê `.env` automaticamente.
BDI recebe mundo e missão estruturada; LLM-only recebe pedido natural e mundo;
no híbrido, `interpret.output["mission"]` transfere a interpretação ao BDI.

O mundo, os oito casos, os prompts logísticos e as regras foram preservados.
Os consumidores Docker históricos reutilizam os agentes e domínio movidos;
os adaptadores antigos de cliente estão em [legacy.py](legacy.py).

## Coletar uma campanha

Após a primeira execução preparar `.tg/bin`, colete os oito casos BDI com
duas repetições:

```sh
uv run --project sdk/python python -m studies.logistics.campaign
```

Para comparar as três estratégias, com chamadas LLM reais:

```sh
uv run --project sdk/python --extra llm python -m studies.logistics.campaign \
  --strategies bdi-only llm-only hybrid --repeat 2
```

A campanha intercala estratégias por caso e repetição. Salva `campaign.json`
e execuções em `.tg/campaigns/logistics-.../runs/`, com processos novos em cada
observação. `--cases` seleciona IDs, `--runtime-dir` escolhe binários e `--output`
escolhe a pasta de campanhas. Falhas e interrupções ficam registradas. Nenhuma
figura é gerada durante a coleta.

Essa política difere de `tg run --repeat N`, que reutiliza processos. Campanhas
têm seu próprio ponteiro de última execução; consulte uma observação pelo
caminho informado no terminal, por exemplo `./tg status CAMINHO/DA/EXECUCAO`.

## Avaliar as evidências

O avaliador usa somente a biblioteca padrão do Python:

```sh
python3 -m studies.logistics.evaluate .tg/runs/tg-ID
python3 -m studies.logistics.evaluate .tg/campaigns/logistics-ID
```

Substitua os IDs pelos caminhos reais. É possível fornecer várias entradas.
Uma pasta nova em `.tg/evaluations` recebe `logistics-results.json`,
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

O BDI declara entradas e um plano em [bdi.py](bdi.py), usando a busca genérica
do SDK por meio de [planning.py](planning.py). O avaliador conserva sua busca
de referência em `domain.py`; as regras de domínio ainda são compartilhadas.
A otimalidade agregada inclui rejeições corretas. Preserve a revisão do avaliador para reproduzir
uma análise. Tokens nos resultados podem não incluir tentativas que falharam
antes de retornar metadados.

Todas as estratégias novas usam workflows. Suas latências não têm exatamente
o mesmo escopo das tarefas simples do benchmark histórico. Os resultados em
`studies/benchmarks/results/logistics-20261004T-final-v2` preservam os conteúdos
da coleta histórica, antes localizada em `benchmarks/results/`. Os runners
antigos continuam disponíveis para reprodução histórica.

## Verificar

```sh
uv run --project sdk/python --extra llm python -m unittest \
  studies.logistics.test_domain studies.logistics.test_study -q
```

Com `TG_TEST_RUNTIME_DIR="$PWD/.tg/bin"`, inclui integração híbrida com Go real
e cliente LLM falso, identificado como `test-only`. Esse teste não é resultado
experimental de uma LLM real.

[Avaliação do TCC](../../docs/evaluation.md) · [Interface declarativa](../../docs/experiments.md)

A coleta usa `tg_sdk.campaign`, compartilhado com outros estudos. Execuções
registram revisão, pacotes e hashes de mundo/casos; a avaliação registra seu
código e hashes das evidências. Veja [proveniência](../../docs/consolidation.md).
