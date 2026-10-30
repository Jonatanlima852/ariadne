# Logística v3: o estudo como missão

Versão corrente do estudo logístico: o mesmo domínio e os mesmos casos da
v2, executados como missão no laço do orquestrador Go.

## Pergunta

Um planejador LLM coordenando entregadores BDI em paralelo atende melhor os
pedidos, com menos chamadas e tokens, do que um único LLM decidindo todas as
ações, quando ambos rodam como missões sob o mesmo runtime?

## Como funciona

A v3 responde à crítica feita à v2: o laço de episódio saiu do controlador
Python e passou a ser o laço de missão do orquestrador Go (contrato 2.0.0).
O domínio (estado, transições, incidentes, métricas) e os casos são os da
[v2](../v2/README.md), importados sem alteração. Duas configurações rodam
como missões e compartilham runtime, evidências e visualizador:

| Configuração | Planejador (capacidade) | Passos de cada rodada |
|---|---|---|
| `ariadne-v3` | LLM `mission-planning` | um `plan-delivery` por pedido atacado agora (agentes BDI `logistics-v3-delivery`, em paralelo) e um `execute` final (`logistics-v3-execute`) que recebe as propostas por bindings |
| `single-llm-v3` | LLM `logistics-v3-single-llm` (mesmo prompt da v2) | um único `execute` com as ações que o modelo decidiu |

O planejador LLM interpreta os pedidos em linguagem natural, decide quais
atacar em paralelo e com que veículo, e replaneja ao ver no contexto o novo
estado e os incidentes que o executor disparou. Cada entregador BDI delibera
sobre um pedido (`direct_delivery`, `load_from_other_depot`,
`recharge_then_deliver`, `continue_with_cargo`,
`transfer_from_disabled_vehicle`) usando as buscas da v2 e devolve a
sequência de ações proposta com o rastro; um pedido inviável volta como
`feasible=false` com o motivo. O executor aplica as propostas na ordem do
plano, rejeita ações inválidas e dispara incidentes antes da próxima ação.

| Caminho | Responsabilidade |
|---|---|
| `domain/` | Adaptadores do domínio da v2 ao laço de missão e leitura dos casos |
| `agents/` | `planner` (LLM), `single_llm` (LLM), `delivery` (BDI), `execute` (determinístico), cada um com Dockerfile |
| `mission.py` | Declaração da missão por caso/configuração e métricas do `MissionResult` |
| `scenario.py` | Um caso como missão declarada; `./ariadne run` sobe planejador, entregadores e executor em contêineres |
| [campaign.py](campaign.py) | Matriz de casos e configurações para `./ariadne campaign` |
| [analysis.py](analysis.py) | Linhas por missão, verificação do provedor e comparação reutilizando o analisador da v2 |

## Executar

Sem credencial (substitutos determinísticos; não mede um modelo):

```sh
LOGISTICS_V3_DEMO=1 LOGISTICS_V3_CASE=vehicle-loss ./ariadne run studies/scenarios/logistics/v3/scenario.py
LOGISTICS_V3_DEMO=1 LOGISTICS_V3_CONFIGURATION=single-llm-v3 ./ariadne run studies/scenarios/logistics/v3/scenario.py
```

Com modelo real, exporte `OPENAI_API_KEY` (e `LLM_MODEL` opcional) e omita
`LOGISTICS_V3_DEMO`. Cada execução fica em `runs/`; o `mission-result.json`
abre em `./ariadne viewer`.

## Variáveis

| Variável | Padrão | Efeito |
|---|---|---|
| `LOGISTICS_V3_CASE` | `easy` | Caso das suítes `basic` ou `stress` |
| `LOGISTICS_V3_CONFIGURATION` | `ariadne-v3` | `ariadne-v3` ou `single-llm-v3` |
| `LOGISTICS_V3_DEMO` | `0` | `1` usa os substitutos determinísticos |
| `LLM_MODEL` | `gpt-5.6-luna` | Modelo pedido ao provedor no modo real |
| `LOGISTICS_V3_CAMPAIGN_SUITE` | `basic` | Suíte da campanha: `basic`, `stress` ou `all` |
| `LOGISTICS_V3_CAMPAIGN_CASES` | todos da suíte | IDs de casos da campanha |
| `LOGISTICS_V3_CAMPAIGN_CONFIGURATIONS` | `ariadne-v3 single-llm-v3` | Configurações da campanha |
| `LOGISTICS_V3_CAMPAIGN_REPEAT` | `1` | Repetições por combinação |

## Repetir e analisar

```sh
LOGISTICS_V3_CAMPAIGN_SUITE=stress LOGISTICS_V3_CAMPAIGN_REPEAT=3 \
  ./ariadne campaign studies/scenarios/logistics/v3/campaign.py
python -m studies.scenarios.logistics.v3.analysis \
  studies/scenarios/logistics/v3/campaigns/campaign-<id> --no-plots
```

Cada observação sobe e derruba sua própria topologia. A análise transforma
cada `mission-result.json` em uma linha (`results.json`, `comparison.md`),
confere o provedor do planejador e reutiliza o analisador da v2 para as
tabelas e figuras; com `LOGISTICS_V3_DEMO=1` a mesma campanha usa os
substitutos.

## Limites

Não há resultados reais da v3 registrados ainda. Em modo demo nada é medido
sobre um modelo.

[Estudo logístico](../README.md) · [Todos os estudos](../../../README.md)
