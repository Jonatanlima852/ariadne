# Mission Viewer

Página estática que desenha a execução de uma missão como quadros ligados por
setas: em cada rodada, a chamada ao planejador seguida dos passos do plano.
Clicar num quadro mostra a entrada e a saída daquela chamada exatamente como
estão no JSON do contrato. Nada além disso: sem replay, sem gráficos, sem
exportação.

## Como abrir as execuções

A fonte é sempre `.ariadne` deste repositório, mais os resultados
preservados dos estudos; não é preciso escolher pasta.

1. `make viewer` (ou `python3 tools/mission-viewer/serve.py`, da raiz do
   repositório). Um servidor de biblioteca padrão indexa
   `.ariadne/runs/*/mission-result.json`,
   `.ariadne/logistics-v3/*/missions/*.json`, `.ariadne/campaigns/**`,
   `studies/**/results/**/missions/*.json` e `fixtures/`, e abre o
   navegador em `http://127.0.0.1:4180/`. O botão "Atualizar" relê o
   índice depois de novas execuções. Outras pastas: `--root PASTA`
   (repetível); outra porta: `--port`; sem abrir o navegador:
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
estático), `&node=<step_id>` ou `&node=round-<n>-planner` abre a gaveta
naquele quadro, `&tab=0|1|2` escolhe Entrada, Saída ou Rastro, e
`&theme=dark|light` força o tema.

## A lista

Barra lateral recolhível (botão "Lista"; ela se recolhe ao escolher uma
missão e o estado fica em `localStorage`). Uma linha por missão, da mais
recente para a mais antiga, com filtro de texto: objetivo (`request.goal`),
estado, caso e suíte (`request.metadata.case`/`suite` ou
`request.context.case`), configuração (`request.metadata.configuration`),
cenário (pasta do `source` do `manifest.json`, senão
`request.metadata.study`, senão `request.trace.correlation_id`),
`created_at`, número de rodadas, duração e o caminho do arquivo. A última
missão aberta e o tema também ficam em `localStorage`.

## O grafo

- Cada rodada é uma faixa que diz o que aconteceu ("Rodada 2: o planejador
  propôs 3 passos", "Rodada 4: o planejador encerrou a missão (DONE)") e
  traz a ação (`PLAN`, `DONE`, `ABORT`) e o resumo que ele devolveu. O
  cabeçalho lembra: cada rodada é uma chamada ao planejador seguida dos
  passos que ele propôs; a missão termina quando ele responde `DONE`.
- Coluna 0 da faixa: o planejador. Colunas seguintes: passos por
  profundidade no DAG (`depends_on`); passos da mesma profundidade ficam um
  abaixo do outro porque podem executar em paralelo.
- Cada quadro traz o `step_id`, a capacidade exigida, o agente que executou,
  a duração e, quando `attempt > 1`, o selo "reatribuído". A barra à
  esquerda é o estado: `completed`, `failed`, `skipped`, `cancelled`,
  `timeout`, `pending`.
- Setas: planejador para os passos sem dependência, `depends_on` entre
  passos, e uma seta tracejada entre os planejadores de rodadas seguidas.
- Teclado: setas trocam o quadro selecionado, Enter abre, Esc fecha a gaveta.

A gaveta tem as abas Entrada (`Task` ou `PlannerRequest`), Saída
(`TaskResult` ou `PlannerResponse`) e, quando o resultado traz
`bdi.trace.cycles`, Rastro BDI com um ciclo por linha. O JSON vem colorido e
com objetos grandes recolhidos; o botão Copiar JSON copia a aba atual.

## Entrada esperada

O arquivo gravado por `MissionResult.save(path)` do SDK Python, que o executor
declarativo (`./ariadne run experimento.py`) salva como `mission-result.json`
nas evidências e a campanha da logística v3 salva em `missions/*.json`. É o
`MissionResult` do contrato 2.0.0 em JSON com nomes de campo do proto
(snake_case), mais duas chaves do SDK:

| Chave | Origem | Uso no visualizador |
|---|---|---|
| `mission_id`, `status`, `output`, `context`, `rounds[]`, `error`, `trace`, `created_at`, `completed_at`, `root_task_id` | `MissionResult` | resumo, lista e rodadas |
| `rounds[].plan.steps[].depends_on` | `WorkflowDefinition` | setas entre passos |
| `rounds[].result.step_results[].task` | `WorkflowStepResult.task` | entrada de um passo, capacidade e tentativa |
| `rounds[].result.step_results[].result` | `WorkflowStepResult.result` | saída de um passo, agente, duração, cor do quadro (`status`) e rastro BDI |
| `rounds[].planner_task.payload` | `Task` enviada ao planejador | entrada do planejador (`PlannerRequest`, com `available_capabilities`) |
| `rounds[].planner_result.output` | `TaskResult` do planejador | saída do planejador (`PlannerResponse`) |
| `request` | `MissionRequest` enviado pelo cliente | objetivo, `metadata` e `context.case` na lista |
| `planner_calls[].request` | `planner_task.payload`, ou reconstruído pelo SDK | entrada do planejador quando a rodada não traz `planner_task` |
| `planner_calls[].response` | `planner_result.output` | saída do planejador |

Um `WorkflowResult` do contrato (`step_results` na raiz) é desenhado como uma
única rodada sem quadro de planejador; sem `plan.steps` ou
`definition.steps` não há setas de dependência. O `result.json` do executor
declarativo (`steps` como objeto) também abre, só com os resultados, mas não
entra na lista.

## Exemplos

- `fixtures/mission-result.json`: três rodadas (dois `PLAN`, com passos
  concluídos, falho e pulado, e um `DONE`), gerado com mensagens reais do
  contrato por `MissionResult.save`.
- `fixtures/logistics-v3-vehicle-loss-demo.json`: caso `vehicle-loss` da
  logística v3 rodado localmente, quatro rodadas com passos paralelos e
  rastro BDI.
