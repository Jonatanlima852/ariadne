# Incêndio florestal: comandante LLM com drones BDI contra um piloto LLM

Uma grade pega fogo; o vento espalha as chamas; drones com água e bateria
apagam focos e reabastecem em bases; o rádio anuncia, em linguagem natural,
fatos que a telemetria não mostra. O mesmo LLM, com a mesma vista, decide em
dois níveis: como comandante de drones BDI ou como piloto de cada drone.

## Pergunta

Um LLM que comanda drones BDI (metas e crenças por rodada) contém o incêndio
melhor, com menos ações inválidas, menos drones perdidos e menos tokens, do
que o mesmo LLM pilotando cada drone diretamente, quando ambos rodam como
missões sob o mesmo runtime?

## Como funciona

O cenário é uma missão do contrato 2.0.0: cada rodada do laço do
orquestrador é um tique do mundo. O estado inteiro viaja no contexto da
missão e é substituído a cada rodada pela saída do passo final.

| Configuração | Planejador (capacidade) | Passos de cada rodada |
|---|---|---|
| `ariadne` | LLM `mission-planning` (comandante): uma meta por drone (`attack`, `protect`, `resupply`, `return`, `hold`, `auto`) e crenças compartilhadas (`disabled_bases`, `priority_cells`) | um `drone-<id>` por drone ativo (agentes BDI `wildfire-drone`, em paralelo) e um `world` final (`wildfire-world`) que recebe as ações por bindings |
| `single-llm` | LLM `wildfire-single-llm` (piloto): uma ação concreta por drone (`move`, `drop`, `resupply`, `hold` com alvo) | um único `world` com as ações inline |

Os dois planejadores leem exatamente a mesma vista (focos com intensidade,
cinzas, bases, drones, rádio e o relatório da rodada anterior), as mesmas
regras em texto e o mesmo modelo; o vocabulário de ações é idêntico. A
diferença é só quem decide a ação de cada drone.

**Mundo** ([domain/world.py](domain/world.py)). Grade `width × height`,
células `"x,y"`, x para leste e y para sul. Um foco tem intensidade 1 a 3,
sobe 1 por tique e vira cinzas (perda permanente) no tique seguinte ao 3.
Espalha uma célula a favor do vento com intensidade ≥ 2 (≥ 1 com vento 2),
para as laterais com intensidade 3, nunca contra o vento. Obstáculos, cinzas
e bases não queimam; estruturas queimam como vegetação. Drones voam até 4
células por tique por um caminho que evita obstáculos (1 de bateria por
célula), soltam água numa célula vizinha (1 água, 1 bateria, intensidade
−3), reabastecem só em base ativa (água cheia, +20 de bateria, máximo 40) ou
aguardam. Bateria zero fora de base ativa: drone perdido. Tudo é
determinístico: a mesma sequência de ações produz o mesmo resultado.

**Rádio e verdade oculta.** Eventos agendados por caso levam uma mensagem em
português e efeitos. Efeitos visíveis (vento, drones fora do ar) entram no
estado. Efeitos de rádio (base destruída, hospital a proteger) não entram:
a telemetria continua mostrando a base ativa, e só o executor, recompondo a
agenda do caso (`truth_at`), rejeita reabastecer nela. O LLM precisa ler o
rádio nos dois braços; no híbrido, ele traduz o texto em crenças e metas
para os drones.

**Drone BDI** ([agents/drone/main.py](agents/drone/main.py)). Uma tarefa por
drone e por tique, objetivo `act(drone)`, planos com condição de contexto e
custo fixo: `stand_down`, `hold_ordered`, `resupply_here`, `return_to_base`,
`attack_target`, `guard_target`, `attack_nearest` e `hold_position`. A reserva
de bateria é condição de contexto: o drone nunca escolhe um alvo de onde não
consiga voltar a uma base utilizável, e bases que o comandante marcou como
mortas não contam. Os drones deliberam em paralelo sem se falar; como veem
as mesmas posições, aplicam uma convenção de posto: se `r` outros drones
estão tão perto do melhor foco quanto este, ele cede e começa pelo
`r`-ésimo seguinte; vizinhos a até duas células repartem as células em
chamas adjacentes pela mesma convenção, em ordem de id. Sem o comandante
(ordens `auto`), o BDI ataca o foco seguro mais próximo, prioritários
primeiro. O caminho é a busca de custo
uniforme do SDK; o rastro de deliberação vai no `TaskResult.bdi`.

**Mundo como agente** ([agents/world/main.py](agents/world/main.py)). Aplica
as ações na ordem do plano, rejeita as inválidas com motivo, derruba drones
sem bateria, avança o fogo, incrementa o tique e dispara os eventos; devolve
estado, relatório e só o texto do rádio. Atalhos sem modelo: sem fogo ou
horizonte atingido, o planejador responde `DONE`.

## Executar

Sem credencial (substitutos determinísticos; não mede um modelo):

```sh
WILDFIRE_DEMO=1 ./ariadne run studies/scenarios/wildfire/scenario.py
WILDFIRE_DEMO=1 WILDFIRE_CASE=hospital-alert WILDFIRE_CONFIGURATION=single-llm ./ariadne run studies/scenarios/wildfire/scenario.py
```

Com modelo real, exporte `OPENAI_API_KEY` (e `LLM_MODEL` opcional) e omita
`WILDFIRE_DEMO`. Cada execução fica em `runs/`; o `mission-result.json` abre
em `./ariadne viewer`, com rótulos de apresentação para cada agente e passo.

## Variáveis

| Variável | Padrão | Efeito |
|---|---|---|
| `WILDFIRE_CASE` | `three-fronts` | `single-fire`, `three-fronts`, `windy` (suíte `basic`), `hospital-alert` (`alert`), `storm` (`stress`) |
| `WILDFIRE_CONFIGURATION` | `ariadne` | `ariadne` ou `single-llm` |
| `WILDFIRE_DEMO` | `0` | `1` usa os substitutos determinísticos |
| `WILDFIRE_DRONES` | do caso | sobrepõe o número de drones (até 9: o plano aceita 10 passos e um é o mundo) |
| `WILDFIRE_DRONE_AGENTS` | `4` | contêineres de drone BDI que servem os passos `drone-*` em rodízio |
| `WILDFIRE_COMMAND_EVERY` | `1` | cadência do comandante; com N > 1, só chama o modelo na rodada 1, quando há novidade (rádio, rejeição, perda) ou a cada N rodadas, e repete as ordens anteriores nas demais |
| `LLM_MODEL` | `gpt-5.6-luna` | modelo pedido ao provedor no modo real |
| `WILDFIRE_CAMPAIGN_SUITE` | `all` | suíte da campanha: `basic`, `alert`, `stress` ou `all` |
| `WILDFIRE_CAMPAIGN_CASES` | todos da suíte | IDs de casos da campanha |
| `WILDFIRE_CAMPAIGN_CONFIGURATIONS` | `ariadne single-llm` | configurações da campanha |
| `WILDFIRE_CAMPAIGN_DRONES` | nenhuma | varredura do número de drones, por exemplo `2 4 8` |
| `WILDFIRE_CAMPAIGN_REPEAT` | `1` | repetições por combinação |

| Caso | Suíte | Grade | Drones | Focos | Eventos |
|---|---|---|---:|---:|---|
| `single-fire` | basic | 12×12, 10 tiques | 2 | 1 | nenhum |
| `three-fronts` | basic | 16×16, 16 tiques | 4 | 3 | escola visível a favor do vento |
| `windy` | basic | 16×16, 16 tiques | 4 | 4 | vento 2 desde o início; linha de torres como obstáculo |
| `hospital-alert` | alert | 16×16, 18 tiques | 6 | 6 | tique 5: hospital só no rádio, base norte fora de serviço, vento vira para leste |
| `storm` | stress | 20×20, 20 tiques | 8 | 10 | tique 4: hospital e base; tique 8: vento dobra; tique 12: dois drones fora do ar |

## Repetir e analisar

```sh
WILDFIRE_CAMPAIGN_SUITE=all WILDFIRE_CAMPAIGN_REPEAT=3 \
  ./ariadne campaign studies/scenarios/wildfire/campaign.py
uv run --project sdk/python --extra llm python -m studies.scenarios.wildfire.analysis \
  studies/scenarios/wildfire/campaigns/campaign-<id>
```

Cada observação sobe e derruba sua própria topologia. A análise transforma
cada `mission-result.json` em uma linha (`results.json`, `observations.csv`),
confere o provedor do planejador, grava `comparison.md` com as médias por
caso e configuração e a diferença pareada, e desenha as figuras em SVG; com
matplotlib disponível (`uv run --with matplotlib ...`), também PNG e um GIF
por missão. `--no-plots` fica só nos SVG. `WILDFIRE_CAMPAIGN_DRONES="2 4 8"`
com `WILDFIRE_CAMPAIGN_CASES=storm` faz a varredura de escala.

Sem Docker, os testes rodam o mesmo laço em processo
([loop.py](loop.py) imita o orquestrador: planejador, passos, bindings,
mescla do contexto) com os substitutos, para validar agentes, métricas e
análise. Não é um modo de execução do estudo.

```sh
uv run --project sdk/python --extra llm python -m unittest \
  studies.scenarios.wildfire.test_world studies.scenarios.wildfire.test_agents -q
```

## Como ler as figuras

- `curves-<caso>.svg`: células em cinzas por tique; uma linha fina por
  observação e a média em negrito por configuração (azul: Ariadne; laranja:
  piloto LLM). Quanto mais baixa e mais cedo estabiliza, melhor.
- `frames-<caso>-<configuração>.svg` e `.gif`: a grade no início, a um
  quarto, à metade, a três quartos e no fim de uma missão. Laranja a vermelho
  é fogo por intensidade; cinza escuro é cinzas; quadrados azuis são bases
  (cinza quando o rádio as tirou de serviço); roxo é estrutura (vazada quando
  queimou, inclusive as anunciadas só pelo rádio); círculos são drones; `×`
  é drone perdido.
- `summary.svg`: área queimada ao final, em porcentagem das células, por caso
  e configuração.
- `player-<caso>.html` ([player.py](player.py)): página autônoma com as duas
  configurações lado a lado, dia a dia (cada tique do mundo aparece como um
  dia). No alto, o rádio mostra o aviso que chegou naquele dia, ou o último
  ainda em vigor: é o que o modelo precisa interpretar. Em cada painel: a
  grade (drones `d1…` com arco de bateria, pontos de água, rastro e gota;
  bases `B1…`; estruturas `H`/`E`, tracejadas quando só o rádio as anunciou;
  passar o mouse numa célula mostra o que há nela), uma linha com o que mudou
  no dia (gotas, focos apagados, avanço do fogo, rejeições), o resumo e as
  ordens do comandante ou as ações do piloto, e por drone a decisão (plano
  BDI) e a resposta do mundo, com os nomes técnicos traduzidos. `player.html`
  abre qualquer `mission-result.json` pelo botão ou arrastando; `?dia=N` e
  `?play=1` na URL escolhem o instante.
- `comparison.md`: cinzas, focos restantes, estruturas perdidas, drones
  perdidos, ações rejeitadas e ociosas, missões contidas, reação ao alerta
  (tiques entre o anúncio e o primeiro drone a até duas células do hospital),
  chamadas e tokens do modelo, tempo de parede; e a diferença pareada.

## Limites

Mostra: o mesmo modelo, com a mesma vista, em dois níveis de decisão sob o
mesmo laço de missão; a camada BDI garante por construção a reserva de
bateria e traduz crenças do comandante em ações válidas; o custo em chamadas
e tokens de cada nível; o efeito de um alerta em linguagem natural que a
telemetria não reflete.

Não mostra: tempo real (o fogo avança um tique por rodada, igual para os dois
braços; latência e tokens são custos medidos à parte, não aceleram o fogo);
mensagens entre drones dentro de uma rodada (a convenção de posto substitui
um leilão); física, névoa de guerra ou papéis de drone além de bombeiros.
O espalhamento é determinístico e as regras são simples; os números medem
este mundo, não um incêndio real. Em modo demo, o comandante substituto lê o
rádio com expressões regulares e dá ordens `auto`: a comparação demo mostra
a camada BDI contra uma política gulosa, não um modelo. O braço híbrido
funciona mesmo com um comandante pouco atento, porque os drones BDI têm
comportamento local próprio; esse é um resultado da arquitetura e deve ser
lido como tal. Não há resultados reais preservados ainda.

[Todos os estudos](../../README.md) · [Avaliação do TCC](../../../docs/evaluation.md)
