# Logística v1

Estudo original: um pedido em linguagem natural vira uma missão estruturada
e um plano validado por um simulador. É a primeira de três versões; a
[v3](v3/README.md) é a corrente e a [v2](v2/README.md) é histórica.

## Pergunta

Interpretar com LLM e planejar com BDI (híbrido) produz planos melhores do
que pedir tudo ao LLM, no mesmo mundo e nos mesmos casos?

## Como funciona

[scenario.py](scenario.py) declara os participantes e o workflow fixo: no
híbrido, `interpret` (LLM) extrai restrições e `execute` (BDI) planeja a
missão recebida por binding; em LLM-only, uma etapa recebe o pedido e o
mundo e propõe as ações. [analysis.py](analysis.py) avalia as evidências
depois, com um simulador independente, sem iniciar serviços.

| Pasta/entrada | O que ler aqui |
|---|---|
| `scenario.py` | Declaração do estudo, agentes e tarefas |
| `domain/` | Simulação de referência e adaptação ao planejador do SDK |
| `datasets/` | Mundo, casos fixos e carregamento de dados |
| `agents/` | Interpretação LLM e planejamento BDI |
| `campaign.py` | Matriz de casos e estratégias para `./ariadne campaign` |
| `analysis.py` | Avaliação offline das evidências |
| `evaluation/` | Relatórios e proveniência usados pela análise |
| `results/` | Coleta histórica preservada |

## Executar

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
configurado por `LLM_MODEL`; o executor repassa as duas aos contêineres e não lê `.env`.
LLM-only recebe pedido natural e mundo;
no híbrido, `interpret.output["mission"]` transfere a interpretação ao BDI.

O mundo, os oito casos, os prompts logísticos e as regras foram preservados.

## Variáveis

| Variável | Padrão | Efeito |
|---|---|---|
| `LOGISTICS_CASE` | `avoid-contamination` | Caso do dataset |
| `LOGISTICS_STRATEGY` | `hybrid` | `hybrid` ou `llm-only` |
| `LLM_MODEL` | `gpt-5.6-luna` | Modelo pedido ao provedor |
| `LOGISTICS_CAMPAIGN_CASES` | todos | Casos da campanha |
| `LOGISTICS_CAMPAIGN_STRATEGIES` | `hybrid` | Estratégias da campanha |
| `LOGISTICS_CAMPAIGN_REPEAT` | `2` | Repetições por combinação |

## Repetir e analisar

Colete os oito casos híbridos com duas repetições (uma topologia em
contêineres por observação):

```sh
ARIADNE_SDK_EXTRAS=llm ./ariadne campaign studies/scenarios/logistics/campaign.py
```

Para comparar as duas estratégias, com chamadas LLM reais:

```sh
LOGISTICS_CAMPAIGN_STRATEGIES="llm-only hybrid" ARIADNE_SDK_EXTRAS=llm \
  ./ariadne campaign studies/scenarios/logistics/campaign.py
```

A campanha alterna estratégias dentro de cada caso. Salva `campaign.json` e
as execuções em `campaigns/campaign-<id>/runs/`, ao lado deste README, com uma
topologia nova em cada observação. `LOGISTICS_CAMPAIGN_CASES` seleciona IDs e
`LOGISTICS_CAMPAIGN_REPEAT` as repetições. Falhas e interrupções ficam
registradas. Nenhuma figura é gerada durante a coleta.

Essa política difere de `ariadne run --repeat N`, que reutiliza processos. Campanhas
têm seu próprio ponteiro de última execução; consulte uma observação pelo
caminho informado no terminal, por exemplo `./ariadne status CAMINHO/DA/EXECUCAO`.

O avaliador usa somente a biblioteca padrão do Python:

```sh
python3 -m studies.scenarios.logistics.analysis studies/scenarios/logistics/runs/ariadne-ID
python3 -m studies.scenarios.logistics.analysis studies/scenarios/logistics/campaigns/campaign-ID
```

Substitua os IDs pelos caminhos reais. É possível fornecer várias entradas.
Uma pasta nova `analysis-<id>` dentro da primeira entrada recebe
`logistics-results.json`, `logistics-summary.csv` e `logistics-quality.svg`.
`--output caminho-novo` seleciona outro destino; um destino existente é
rejeitado. Entradas não mudam.

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
`studies/scenarios/logistics/results/logistics-20261004T-final-v2` preservam os conteúdos
da coleta histórica. Os arquivos preservados incluem BDI-only da coleta antiga; os runners atuais
executam somente LLM-only e híbrido. A leitura das evidências antigas continua
disponível no avaliador, sem recolher BDI isolado.

## Resultados preservados

`results/logistics-20261004T-final-v2` preserva a coleta histórica de 4 de
outubro de 2026 (oito casos, duas repetições, `gpt-5.6-luna`), citada no
[guia de avaliação](../../../docs/evaluation.md). Inclui BDI-only, que a
coleta atual não executa.

## Limites

O avaliador compartilha regras de domínio com o BDI; a execução usa a busca
genérica do SDK e a avaliação conserva uma busca de referência. A
otimalidade agregada inclui rejeições corretas. Tokens podem não incluir
tentativas que falharam antes de retornar metadados. As latências dos
workflows não têm o mesmo escopo das tarefas simples da coleta histórica.

[Todos os estudos](../../README.md) · [Avaliação do TCC](../../../docs/evaluation.md) · [Proveniência](../../../docs/experiments.md#proveniência)
