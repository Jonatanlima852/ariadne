# Figuras do percurso dos agentes

Os dois exemplos abaixo foram exportados de execuções com LLM real. Os arquivos
HTML funcionam offline, com botões de reprodução, passos, seleção de quadro,
velocidade e download do SVG atual. Os PNGs têm 1600 × 900 pixels; os SVGs são
vetoriais. Os GIFs reproduzem todos os quadros em 1280 × 720, em ritmo didático.

| Exemplo | Para slides | Percurso | Evidência |
| --- | --- | --- | --- |
| Arquitetura original, dez agentes: `s07-loaded-vehicle-loss` | [Panorama PNG](s07-ariadne/overview.png), [SVG](s07-ariadne/overview.svg), [pane](s07-ariadne/incident.png), [recuperação da carga](s07-ariadne/recovery.png) | [HTML offline](s07-ariadne/flow.html), [GIF](s07-ariadne/flow.gif) | [Episódio](s07-ariadne/episode.json), [quadros](s07-ariadne/frames.json), [proveniência](s07-ariadne/provenance.json) |
| Arquitetura enxuta, oito agentes: `s08-cascading-disruptions` | [Panorama PNG](s08-ariadne-lean/overview.png), [SVG](s08-ariadne-lean/overview.svg), [indisponibilidade](s08-ariadne-lean/incident.png), [recuperação da carga](s08-ariadne-lean/recovery.png) | [HTML offline](s08-ariadne-lean/flow.html), [GIF](s08-ariadne-lean/flow.gif) | [Episódio](s08-ariadne-lean/episode.json), [quadros](s08-ariadne-lean/frames.json), [proveniência](s08-ariadne-lean/provenance.json) |

No exemplo original, a pane de `van1` ocorre no minuto simulado 1, após o
carregamento. O incidente é analisado, a missão é decomposta novamente e `van2`
recupera `o1` por `TRANSFER` no minuto 7. O estado final registra 6/6 entregas
no prazo, 33 ações aceitas e 62 minutos simulados. São 47 chamadas aos agentes,
incluindo cinco chamadas LLM, e sete workflows. O percurso tem 59 quadros.

No exemplo enxuto, dez pedidos enfrentam três ocorrências: indisponibilidade
de `van1` no minuto 3, bloqueio E–F no minuto 12 e bloqueio I–N no minuto 32.
O `MissionCoordinator` BDI atualiza a missão a partir do estado e do feedback;
`van2` recupera a carga de `o1` por `TRANSFER` no minuto 7. O estado final
registra 10/10 entregas no prazo e 121 minutos simulados. Este episódio usa
uma chamada LLM para interpretação e sete agentes BDI. O percurso tem 113
quadros. É um piloto da variante enxuta, não uma comparação estatística com
o exemplo original, que usa outro caso.

As setas sempre ligam um agente ao orquestrador. Elas representam tarefas e
respostas do runtime, sem afirmar mensagens diretas entre especialistas.
Os passos preservam `task_id`, `workflow_id`, a ordem de `calls` e os eventos
de `state.history`. As contagens nos círculos são chamadas acumuladas; o
cabeçalho identifica explicitamente o desfecho final, inclusive durante a
reprodução. O intervalo dos quadros não representa duração real nem
concorrência. O relato textual do LLM não é usado para construir as métricas.

`provenance.json` preserva o caminho e SHA-256 da coleção lida, a seleção,
SHA-256 do episódio e renderizador, trace e IDs. O episódio exportado é um
snapshot: a coleção de origem pode continuar recebendo outras observações.

Há também uma conferência com os eventos efetivos do Orchestrator:
[`s07/runtime-correlation.json`](s07-ariadne/runtime-correlation.json) correlaciona
as 47 chamadas a 239 eventos do trace;
[`s08/runtime-correlation.json`](s08-ariadne-lean/runtime-correlation.json)
correlaciona as 92 chamadas a 458 eventos. Os arquivos `runtime-events.jsonl`
ao lado dos episódios preservam esses eventos e seus IDs. Essa correlação
verifica a origem das chamadas; o ritmo da animação continua didático.

Para regenerar a partir da raiz do repositório:

```sh
node tools/inspector/scripts/export-logistics-flow.mjs \
  --input .ariadne/logistics-v2/20261022T061918320935Z/results.json \
  --case s07-loaded-vehicle-loss --configuration ariadne \
  --output studies/scenarios/logistics/v2/results/presentation/s07-ariadne

node tools/inspector/scripts/export-logistics-flow.mjs \
  --input .ariadne/logistics-v2/20261022T064520956662Z/results.json \
  --case s08-cascading-disruptions --configuration ariadne-lean \
  --output studies/scenarios/logistics/v2/results/presentation/s08-ariadne-lean

uv run --with playwright --with pillow python tools/inspector/scripts/render-logistics-media.py \
  studies/scenarios/logistics/v2/results/presentation/s07-ariadne --gif

uv run --with playwright --with pillow python tools/inspector/scripts/render-logistics-media.py \
  studies/scenarios/logistics/v2/results/presentation/s08-ariadne-lean --gif
```

O renderizador usa Chrome instalado no macOS. Em outro ambiente, passe
`--chrome /caminho/para/chrome`; sem esse executável, usa o Chromium do
Playwright, que precisa estar instalado. A geração de SVG/HTML exige apenas
Node; Playwright/Pillow são usados pelo comando opcional de PNG/GIF, sem
alterar as dependências do projeto.

No Inspector, abra **Logística v2**, selecione um caso e uma observação e use
**Percurso dos agentes**. Há atalhos para ocorrências, revisões e transferência
de carga, além de **Panorama para apresentação** e **Baixar figura SVG**.
