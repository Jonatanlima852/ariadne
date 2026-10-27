# Confirmação: Single LLM e Ariadne enxuta

Foram concluídas **60/60 observações**: dez casos fixos, três repetições e duas configurações, todas com `gpt-5.6-luna` em Docker. O híbrido enxuto teve **tempo médio 17,8 vezes menor**, **94,4% menos tokens nos 29 pares com uso conhecido** e maior atendimento agregado.

| Métrica | Single LLM | Ariadne enxuta |
|---|---:|---:|
| Episódios | 30 | 30 |
| Pedidos entregues | 204/228 (89,47%) | 219/228 (96,05%) |
| Entregues no prazo / pedidos totais | 190/228 (83,33%) | 210/228 (92,11%) |
| Tempo real médio por episódio | 87,08 s | 4,88 s |
| Mediana do tempo real | 69,22 s | 4,84 s |
| Tempo real somado | 2.612,44 s | 146,42 s |
| Tokens médios por episódio, nos mesmos 29 pares conhecidos | 18.395,38 | 1.038,41 |
| Chamadas LLM | 81 | 30 |
| Ações rejeitadas no mundo | 13 | 0 |
| Episódios com erro operacional | 1 | 0 |
| Distância somada | 1.969 | 1.830 |
| Energia de movimento somada | 7.860 | 7.494 |

O atendimento cresceu 6,58 pontos percentuais e a pontualidade sobre todos os pedidos, 8,77 pontos percentuais. Esses resultados descrevem esta suíte. Não há alegação de otimalidade global nem teste de generalização.

## Figuras para usar na apresentação

- [Resumo em PNG, 16:9](analysis/headline.png) e [SVG vetorial](analysis/headline.svg).
- [Tempo e tokens por caso](analysis/single-llm-vs-ariadne-lean-7dfe317c/02-tempo-e-tokens.png).
- [Atendimento e pontualidade por caso](analysis/single-llm-vs-ariadne-lean-7dfe317c/01-atendimento.png).
- [Todas as figuras e tabelas](analysis/analysis.md), [CSV por observação](analysis/observations.csv) e [CSV por caso](analysis/case_summary.csv).
- [Percurso dos oito agentes](../presentation/s08-ariadne-lean/flow.html), [panorama PNG](../presentation/s08-ariadne-lean/overview.png) e [animação GIF](../presentation/s08-ariadne-lean/flow.gif).

As médias nas figuras detalhadas são por caso/configuração e informam seu n válido. O resumo 16:9 e os números agregados de tokens deste documento usam os **mesmos 29 pares** com uso conhecido nos dois lados. A figura detalhada de s08 tem n=2 para tokens do Single e n=3 para o híbrido; ela não fundamenta a redução pareada de 94,4%.

## Os dez casos, sem seleção por resultado

Cada linha inclui as três repetições. Atendimento e pontualidade são contagens somadas; o tempo é a média por episódio.

| Caso | Entregues Single / híbrido | No prazo Single / híbrido | Tempo médio Single / híbrido (s) | Razão dos tempos | Pares com tokens |
|---|---:|---:|---:|---:|---:|
| s01-distributed-mixed-orders | 24/24 / 24/24 | 22 / 24 | 53,00 / 4,82 | 11,0× | 3/3 |
| s02-scarce-stock-coupling | 18/24 / 18/24 | 17 / 18 | 79,91 / 4,90 | 16,3× | 3/3 |
| s03-capacity-and-source | 24/24 / 24/24 | 24 / 24 | 54,06 / 4,92 | 11,0× | 3/3 |
| s04-recharge-detours | 18/18 / 18/18 | 17 / 18 | 66,50 / 4,27 | 15,6× | 3/3 |
| s05-directed-connections | 18/18 / 18/18 | 17 / 18 | 55,23 / 4,04 | 13,7× | 3/3 |
| s06-progressive-roadblocks | 24/24 / 24/24 | 24 / 24 | 139,93 / 5,30 | 26,4× | 3/3 |
| s07-loaded-vehicle-loss | 16/18 / 18/18 | 16 / 18 | 95,71 / 4,11 | 23,3× | 3/3 |
| s08-cascading-disruptions | 18/30 / 30/30 | 16 / 30 | 198,80 / 6,04 | 32,9× | 2/3 |
| s09-deadline-and-priority-pressure | 24/24 / 24/24 | 17 / 15 | 71,34 / 5,89 | 12,1× | 3/3 |
| s10-infeasible-among-feasible | 20/24 / 21/24 | 20 / 21 | 56,34 / 4,53 | 12,4× | 3/3 |

## Timeout e análise de sensibilidade

No caso **s08, repetição 1**, o Single LLM excedeu o limite de 90 segundos da chamada ao provedor. O episódio foi preservado com 0/10 entregas, 90,1927 s e erro `APITimeoutError`. O provedor não devolveu uso de tokens; esses campos permanecem `null`. O híbrido completou esse episódio.

Os totais de atendimento e tempo acima incluem o timeout. Retirando **o par inteiro**, permanecem 29 pares: Single 204/218 entregues e 190 no prazo; híbrido 209/218 entregues e 200 no prazo. A razão dos tempos médios continua em **18,0×**. Portanto, a vantagem de tempo não depende desse timeout.

Os tokens conhecidos somam **533.466 contra 30.114** nos mesmos 29 pares. O total completo do Single é desconhecido, não zero; o híbrido registrou 31.313 tokens nos 30 episódios. Não foi estimado custo monetário.

O manifesto tem status `FAILED` porque uma observação terminou com erro operacional. A cobertura está completa: `finished_observations=60`, `planned_observations=60`, sem observações faltantes. Esse status não significa que a coleta foi interrompida.

## O que melhorou e onde houve perda

- **Pane, s07/r2:** sem erro de infraestrutura, o Single entregou 4/6 e executou quatro ações rejeitadas. A van2 ficou em D com bateria 9, abaixo do custo 10 para E; o caminhão ficou em M com bateria 8 e carga pendente. Houve duas tentativas inválidas de TRANSFER a partir de veículo ainda disponível. O híbrido entregou 6/6 no prazo, com autonomia preservada para acesso a carregador.
- **Incidentes sucessivos, s08:** o híbrido entregou 10/10 nas três repetições. O Single teve 0/10 por timeout, 8/10 com término parcial e 10/10. O episódio parcial não foi classificado como falha de infraestrutura.
- **Prazos, s09:** o Single foi melhor em pontualidade agregada: **17/24 contra 15/24**, com atendimento total nos dois lados. O híbrido também consumiu mais energia nesse caso: **735 contra 645**. A heurística local prioriza a missão e não combina cargas para otimizar globalmente os prazos.
- **Restrições de estoque e capacidade, s02/s10:** o atendimento total é impedido por restrições do domínio. Isso não prova que a quantidade entregue pelo híbrido seja a máxima possível: escolher outra ordem, inclusive sacrificar um pedido mais prioritário, pode alterar o número de pedidos atendidos.

## Condições e interpretação

A variante usa um LLM para interpretar pedidos e sete BDI para coordenação, estoque, recursos, rota, energia, validação e execução. O resumo é calculado das métricas. A política energética exige possibilidade de alcançar algum carregador após a entrega enquanto houver trabalho pendente. Isso evita determinadas situações de falta de autonomia; não antecipa os incidentes futuros.

O Single LLM manteve seu prompt e contrato de ações originais; pode combinar pedidos e revisar o plano. Os dois lados usam os mesmos mundos, requisitos, validador e programação de incidentes, modelo e limites: 20 rodadas, 200 ações por proposta, 90 s por chamada e sem repetição automática do provedor. A segunda repetição inverte a ordem das configurações.

O [protocolo e hashes fixados antes da confirmação](../../experiments/lean-v1-confirmation.json) registram as condições. Os dez casos foram usados no desenvolvimento da variante; três repetições medem variação nesses casos, não generalização para instâncias inéditas. Mudaram tanto a composição dos agentes quanto a política energética: não se isola o efeito causal do runtime.

Parte da economia resulta de o híbrido gerar requisitos e planejar em código, enquanto o Single gera sequências de ações no contrato estruturado. Um contrato mais compacto para o baseline seria outra comparação. A evidência sustenta esta divisão de trabalho no domínio e nas condições documentados.

## Dados e reprodução

- [Resultados preservados](results.json), [tabela de todas as observações](comparison.md), [resumo](summary.json), [manifesto](manifest.json), [proveniência](evidence.json) e [conferência de cobertura, fontes e imagens](verification.json).
- [Detalhes do híbrido e comandos de execução](../../docs/lean.md), [casos fixos](../../datasets/stress.json) e [roteiro de apresentação](../../docs/presentation.md).
- [Resultados de desenvolvimento da equipe original](../stress-original-partial/comparison.md) permanecem separados e identificados como coleta incompleta.

Os 60 históricos foram reproduzidos com as transições do domínio; estados finais e métricas coincidem. Isso verifica consistência e compartilha regras com o planejador, sem constituir um oráculo independente. Os dados brutos e os eventos do runtime permanecem na coleção indicada no manifesto.
