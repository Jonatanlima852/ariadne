# Mission Viewer

Página estática que desenha a execução de uma missão como quadros ligados por
setas: em cada rodada, a chamada ao planejador seguida dos passos do plano.
Clicar num quadro mostra a entrada e a saída daquela chamada exatamente como
estão no JSON do contrato. Nada além disso: sem replay, sem gráficos, sem
exportação.

## Uso

Abra `index.html` no navegador (duplo clique serve; não há servidor, build nem
dependência externa) e carregue o JSON de uma das formas:

- botão "Abrir JSON";
- arrastar o arquivo para a página;
- `index.html?file=fixtures/mission-result.json` quando a pasta é servida por
  um servidor estático, por exemplo `python3 -m http.server` nesta pasta.

## Entrada esperada

O arquivo gravado por `MissionResult.save(path)` do SDK Python, que o executor
declarativo (`./ariadne run experimento.py`) salva como `mission-result.json`
nas evidências. É o `MissionResult` do contrato 2.0.0 em JSON com nomes de
campo do proto (snake_case), mais duas chaves do SDK:

| Chave | Origem | Uso no visualizador |
|---|---|---|
| `mission_id`, `status`, `output`, `context`, `rounds[]`, `error`, `trace`, `created_at`, `completed_at`, `root_task_id` | `MissionResult` | resumo e rodadas |
| `rounds[].plan.steps[].depends_on` | `WorkflowDefinition` | setas entre passos |
| `rounds[].result.step_results[].task` | `WorkflowStepResult.task` | entrada de um passo |
| `rounds[].result.step_results[].result` | `WorkflowStepResult.result` | saída de um passo e cor do quadro (`status`) |
| `rounds[].planner_result.output` | `TaskResult` do planejador | saída do planejador (`PlannerResponse`) |
| `request` | `MissionRequest` enviado pelo cliente | objetivo no resumo |
| `planner_calls[].request` | reconstruído pelo SDK | entrada do planejador (`PlannerRequest`) |
| `planner_calls[].response` | `planner_result.output` | saída do planejador |

`planner_calls[].request` é remontado pelo SDK a partir do objetivo, do
contexto anterior à rodada, do histórico e dos limites; o contrato não guarda
`available_capabilities` no resultado, então essa lista fica vazia.

Um `WorkflowResult` do contrato (`step_results` na raiz) é desenhado como uma
única rodada sem quadro de planejador; como ele não carrega a definição, não
há setas de dependência a menos que o JSON traga `plan.steps` ou
`definition.steps`. O `result.json` do executor declarativo (`steps` como
objeto) também abre, só com os resultados.

## Leiaute

- Coluna 0 de cada rodada: o planejador (rótulo: número da rodada, ação
  `PLAN`/`DONE`/`ABORT`, agente).
- Colunas seguintes: passos por profundidade no DAG (`depends_on`); passos
  da mesma profundidade ficam em linhas, um abaixo do outro, porque podem
  executar em paralelo.
- Setas: planejador para os passos sem dependência, `depends_on` entre
  passos, e uma seta tracejada do planejador de uma rodada ao da seguinte.
- Barra colorida à esquerda do quadro: `completed`, `failed`, `skipped`,
  `cancelled`, `timeout`, `pending`. O planejador usa a ação (`PLAN` azul,
  `DONE` verde, `ABORT` vermelho).

## Exemplo

`fixtures/mission-result.json` foi gerado com mensagens reais do contrato
através de `MissionResult.save`: três rodadas (dois `PLAN`, com passos
concluídos, falho e pulado, e um `DONE`).
