# Mission Viewer

Página estática que desenha a execução de uma missão em duas vistas: um
grafo de dependências (em cada rodada, a chamada ao planejador seguida dos
passos do plano, ligados por setas de dependência de dados) e uma linha do
tempo (uma pista por agente, um bloco por chamada, com o orquestrador
despachando e recebendo cada uma). Clicar num quadro ou bloco mostra a
entrada e a saída daquela chamada exatamente como estão no JSON do
contrato. Nada além disso: sem replay, sem gráficos, sem exportação.

## Como abrir as execuções

A fonte é sempre `.ariadne` deste repositório, mais os resultados
preservados dos estudos; não é preciso escolher pasta.

1. `./ariadne viewer` (ou `python3 tools/mission-viewer/serve.py`, da raiz do
   repositório). Um servidor de biblioteca padrão indexa
   `studies/scenarios/**/runs/*/mission-result.json`, `.ariadne/runs/*/mission-result.json`,
   `.ariadne/logistics-v3/*/missions/*.json`, `.ariadne/campaigns/**`,
   `studies/**/results/**/missions/*.json` e `fixtures/`, e abre o
   navegador em `http://127.0.0.1:4180/`. O botão "Atualizar" relê o
   índice depois de novas execuções. Outras pastas: `--root PASTA`
   (repetível; por exemplo `--root .ariadne/fanout` para os estudos de
   fan-out); outra porta: `--port`; sem abrir o navegador:
   `--no-browser`. Rotas: `/api/runs` (índice JSON das missões) e
   `/api/file?path=...` (um arquivo, restrito às raízes servidas).
2. Sem servidor (por exemplo `index.html` aberto por duplo clique), o rodapé
   da lista oferece "Abrir JSON", "Escolher pasta" (Chrome e Edge: a página
   procura, até quatro níveis abaixo, `mission-result.json`, `*.json` dentro
   de `missions/` e `*.json` na pasta escolhida, lendo `manifest.json` ao
   lado quando existe; Safari e Firefox não têm essa API) e arrastar um
   arquivo para a página.

Parâmetros de URL, úteis para compartilhar: `?file=caminho.json` (relativo à
raiz do repositório com o servidor, ou à pasta da página num servidor
estático), `&view=deps|timeline` escolhe a vista, `&node=<step_id>` ou
`&node=round-<n>-planner` abre a gaveta naquele quadro, `&tab=0|1|2`
escolhe Entrada, Saída ou Rastro, `&theme=dark|light` força o tema e
`&zoom=1.5&pan=-120,-60` abre com aquele zoom e deslocamento (em pixels da
tela) em vez de ajustar à janela.

## Rótulos de apresentação

`Scenario(metadata={"presentation": {...}})` troca os nomes exibidos sem tocar
em eventos, resultados ou identificadores. O Viewer lê o bloco do
`manifest.json` ao lado do `mission-result.json` (ou de
`request.metadata.presentation`, quando a missão o carrega):

```python
metadata={"presentation": {
    "title": "Rota heterogênea",
    "description": "Um planejador LLM decompõe o objetivo e um agente BDI escolhe a rota.",
    "request": "texto do pedido, se diferente do objetivo",
    "agents": {"route-planner-01": {"label": "Planejador de rotas", "role": "BDI: delibera entre rotas"}},
    "steps": {"route": {"label": "Escolher rota"}},
}}
```

Com o bloco presente, o cabeçalho ganha um cartão com título, descrição e a
lista de agentes com seus papéis; os quadros, as pistas da linha do tempo e a
gaveta usam os rótulos, mantendo o identificador original como dica. Sem o
bloco, nada muda. O [cenário de rotas](../../studies/scenarios/routing/scenario.py)
é o exemplo.

## A lista

Barra lateral recolhível (botão "Lista"; ela se recolhe ao escolher uma
missão e o estado fica em `localStorage`). Uma linha por missão, da mais
recente para a mais antiga, com filtro de texto: objetivo (`request.goal`),
estado, caso e suíte (`request.metadata.case`/`suite` ou
`request.context.case`), configuração (`request.metadata.configuration`),
cenário (pasta do `source` do `manifest.json`, senão
`request.metadata.study`, senão `request.trace.correlation_id`),
`created_at`, número de rodadas, duração e o caminho do arquivo. A última
missão aberta, a vista escolhida e o tema também ficam em `localStorage`.

## As duas vistas

O cabeçalho da missão traz o id, o estado, o número de rodadas, a duração, o
objetivo e o seletor "Dependências | Linha do tempo". Nas duas vistas vale
a mesma regra: todas as chamadas partem do orquestrador e voltam a ele;
nenhum agente chama outro agente.

### Dependências

- Cada rodada é uma faixa que diz o que aconteceu ("Rodada 2: o planejador
  propôs 3 passos", "Rodada 4: o planejador encerrou a missão (DONE)") e
  traz a ação (`PLAN`, `DONE`, `ABORT`) e o resumo que ele devolveu.
- Coluna 0 da faixa: o planejador. Colunas seguintes: passos por
  profundidade no DAG (`depends_on`); passos da mesma profundidade ficam um
  abaixo do outro porque podem executar em paralelo.
- Cada quadro traz o `step_id`, a capacidade exigida, o agente que executou,
  a duração, o tipo do agente (ver abaixo) e, quando `attempt > 1`, o selo
  "reatribuído". A barra à esquerda é o estado: `completed`, `failed`,
  `skipped`, `cancelled`, `timeout`, `pending`.
- Setas são bindings: a saída de um passo usada na entrada de outro
  (`depends_on`), e do planejador para os passos sem dependência (o plano
  que ele devolveu). Uma seta tracejada liga os planejadores de rodadas
  seguidas. A legenda lembra que as setas mostram dependências de dados,
  não chamadas entre agentes.

### Linha do tempo

- Pistas: "Orchestrator" no alto, depois uma por `agent_id` que executou
  algo na missão, planejadores primeiro e os demais pela primeira
  atividade. Cada rótulo de pista traz o tipo do agente.
- Eixo do tempo da esquerda para a direita, de `created_at` a
  `completed_at` da missão, com marcas em ms ou s. As rodadas são faixas
  verticais (`rounds[].started_at`/`completed_at`) com o rótulo "Rodada n ·
  PLAN · k passos"; passos sem `started_at` (pulados, pendentes) só contam
  no rótulo.
- Cada chamada é um bloco na pista de quem a executou: o planejador usa
  `planner_result.started_at`/`completed_at` (senão `planner_task.created_at`
  até o fim da rodada); cada passo usa `result.started_at`/`completed_at`.
  Blocos muito curtos mantêm uma largura mínima; blocos lado a lado em
  pistas diferentes executaram em paralelo.
- Da pista do orquestrador desce uma linha fina até o início de cada bloco
  (o despacho) e do fim do bloco sobe outra até o orquestrador (o retorno),
  com pontas pequenas; acima de 40 blocos as linhas ficam mais discretas.
- Quando um passo traz `attempt > 1`, o bloco diz "2ª tentativa" e, se o
  `task.created_at` é anterior ao `started_at` do resultado, a tentativa
  anterior aparece hachurada ("tentativa 1 (timeout/falha)") de
  `created_at` até o início da repetição. É um intervalo inferido: o
  contrato só guarda o resultado final de cada `step_id`, e o agente da
  tentativa anterior não é registrado.
- Passar o mouse mostra o `step_id`, o agente, o tipo, a tentativa, o
  início relativo e a duração; clicar abre a mesma gaveta.

### Tipo do agente

Inferido do `TaskResult` de cada chamada: `LLM` quando há
`metadata.provider`, `llm` ou `metadata.agent_kind = "llm"`; `BDI` quando há
`bdi.trace`, `metadata.bdi_trace`, `metadata.selected_plan` ou
`metadata.agent_kind = "bdi"`; senão `DET` (determinístico). Cada tipo tem
uma família de cor (magenta, verde-água e areia), usada no selo de cada
quadro, no fundo de cada bloco, no rótulo de cada pista, no cabeçalho da
gaveta e na legenda; o estado continua na barra à esquerda. Uma pista
recebe o tipo mais frequente entre as chamadas do agente.

### Zoom, deslocamento e teclado

Nas duas vistas, rolar o mouse (ou pinçar no trackpad) sobre o desenho dá
zoom em torno do cursor, sem tecla modificadora; arrastar o fundo desloca.
Os botões no canto inferior direito fazem "−", "+", "100%" e "Ajustar"
(encaixa o desenho na janela, que é o estado inicial). Teclas: `0` volta a
100%, `+` e `-` ampliam e reduzem, `F` ajusta; setas trocam o quadro
selecionado (esquerda e direita na ordem do desenho, cima e baixo pelo
vizinho mais próximo), Enter abre e Esc fecha a gaveta.

A gaveta tem as abas Entrada (`Task` ou `PlannerRequest`), Saída
(`TaskResult` ou `PlannerResponse`) e, quando o resultado traz
`bdi.trace.cycles`, Rastro BDI com um ciclo por linha. O cabeçalho mostra o
tipo do agente, o agente, a capacidade, a tentativa e a duração. O JSON vem
colorido e com objetos grandes recolhidos; o botão Copiar JSON copia a aba
atual.

## Entrada esperada

O arquivo gravado por `MissionResult.save(path)` do SDK Python, que o executor
declarativo (`./ariadne run experimento.py`) salva como `mission-result.json`
nas evidências e a campanha da logística v3 salva em `missions/*.json`. É o
`MissionResult` do contrato 2.0.0 em JSON com nomes de campo do proto
(snake_case), mais duas chaves do SDK:

| Chave | Origem | Uso no visualizador |
|---|---|---|
| `mission_id`, `status`, `output`, `context`, `rounds[]`, `error`, `trace`, `created_at`, `completed_at`, `root_task_id` | `MissionResult` | resumo, lista, rodadas e extensão do eixo do tempo |
| `rounds[].started_at`, `completed_at` | `MissionRound` | faixas das rodadas na linha do tempo |
| `rounds[].plan.steps[].depends_on` | `WorkflowDefinition` | setas entre passos |
| `rounds[].result.step_results[].task` | `WorkflowStepResult.task` | entrada de um passo, capacidade, `attempt` e `created_at` (início inferido da tentativa anterior) |
| `rounds[].result.step_results[].result` | `WorkflowStepResult.result` | saída de um passo, agente, `started_at`/`completed_at` (bloco e duração), cor do quadro (`status`), tipo do agente (`metadata`, `bdi`, `llm`) e rastro BDI |
| `rounds[].planner_task.payload` | `Task` enviada ao planejador | entrada do planejador (`PlannerRequest`, com `available_capabilities`) |
| `rounds[].planner_result` | `TaskResult` do planejador | saída do planejador (`output` é o `PlannerResponse`), bloco do planejador (`started_at`/`completed_at`) e tipo do agente |
| `request` | `MissionRequest` enviado pelo cliente | objetivo, `metadata` e `context.case` na lista |
| `planner_calls[].request` | `planner_task.payload`, ou reconstruído pelo SDK | entrada do planejador quando a rodada não traz `planner_task` |
| `planner_calls[].response` | `planner_result.output` | saída do planejador |

Um `WorkflowResult` do contrato (`step_results` na raiz) é desenhado como uma
única rodada sem quadro de planejador; sem `plan.steps` ou
`definition.steps` não há setas de dependência. O `result.json` do executor
declarativo (`steps` como objeto) também abre, só com os resultados, mas não
entra na lista. Sem nenhum `started_at`/`completed_at` a linha do tempo
avisa que precisa dessas marcas.

## Exemplos

- `fixtures/mission-result.json`: três rodadas (dois `PLAN`, com passos
  concluídos, falho e pulado, e um `DONE`), gerado com mensagens reais do
  contrato por `MissionResult.save`; na linha do tempo os dois `pick_*`
  correm em paralelo e `route` falha.
- `fixtures/logistics-v3-vehicle-loss-demo.json`: caso `vehicle-loss` da
  logística v3 rodado localmente, quatro rodadas com passos paralelos,
  rastro BDI e os três tipos de agente (planejador LLM, entregadores BDI,
  executor determinístico).
- Os `mission-result.json` do estudo de fan-out com contador instável
  (`.ariadne/fanout/**/sweep-flaky/`) trazem passos com `attempt: 2`, que
  mostram a tentativa anterior hachurada.
