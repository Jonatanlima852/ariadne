#!/usr/bin/env node
/** Export one recorded logistics episode as a portable, offline presentation. */
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const MODULE_PATH = fileURLToPath(new URL('../src/logisticsFlow.js', import.meta.url));
const USAGE = `Uso:
  node tools/inspector/scripts/export-logistics-flow.mjs \\
    --input <results.json> --case <caso> --configuration <ariadne|ariadne-lean|single-llm> \\
    --output <diretorio> [--repetition <numero>]

Seleciona exatamente uma observação; repetition tem padrão 1.
Exporta flow.html, overview.svg, episode.json, frames.json e provenance.json.
O HTML funciona diretamente no navegador, sem servidor nem conexão de rede.
A ordem de reprodução é didática e não representa duração ou concorrência real.
`;

function parseArgs(argv) {
  const options = {};
  const known = new Set(['input', 'case', 'configuration', 'output', 'repetition']);
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === '--help' || argument === '-h') return { help: true };
    if (!argument.startsWith('--')) throw new Error(`Argumento inesperado: ${argument}`);
    const key = argument.slice(2);
    if (!known.has(key)) throw new Error(`Opção desconhecida: ${argument}`);
    if (Object.hasOwn(options, key)) throw new Error(`Opção repetida: ${argument}`);
    const value = argv[++index];
    if (!value || value.startsWith('--')) throw new Error(`Falta o valor de ${argument}.`);
    options[key] = value;
  }
  for (const key of ['input', 'case', 'configuration', 'output']) {
    if (!options[key]) throw new Error(`A opção --${key} é obrigatória.`);
  }
  if (!['ariadne', 'ariadne-lean', 'single-llm'].includes(options.configuration)) {
    throw new Error('--configuration deve ser ariadne, ariadne-lean ou single-llm.');
  }
  const repetition = options.repetition ?? '1';
  if (!/^[1-9]\d*$/.test(repetition) || !Number.isSafeInteger(Number(repetition))) {
    throw new Error('--repetition deve ser um inteiro positivo.');
  }
  return { ...options, repetition: Number(repetition) };
}

const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const unique = (items) => [...new Set(items.filter((value) => typeof value === 'string' && value))];
const json = (value) => `${JSON.stringify(value, null, 2)}\n`;
const scriptJSON = (value) => JSON.stringify(value).replace(/</g, '\\u003c').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);

function createHTML(scene, provenance, moduleSource) {
  const row = scene.row;
  const title = `${row.case} · ${row.configuration}`;
  // A closing script tag can appear inside a source string or comment.
  const inlineModule = moduleSource.replace(/<\/script/gi, '<\\/script');
  return `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>${escapeHTML(title)} · Fluxo de execução</title>
  <style>
    :root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#1c2942;background:#edf1f7;font-synthesis:none}
    *{box-sizing:border-box}body{margin:0}button,input,select{font:inherit}button,select{border:1px solid #c8d2e2;border-radius:8px;background:#fff;color:inherit;padding:9px 12px}button{cursor:pointer}button:hover:not(:disabled){border-color:#3870b7;background:#f5f9ff}button:disabled{opacity:.45;cursor:default}a{color:#245fa9;text-underline-offset:3px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #72a4ed;outline-offset:3px}
    .page{max-width:1800px;margin:0 auto;padding:26px}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-weight:700;font-size:11px;color:#5d6d87;margin:0 0 7px}h1{font-size:clamp(21px,2vw,30px);line-height:1.2;margin:0 0 12px}.intro{max-width:1080px;color:#54647d;font-size:14px;line-height:1.6;margin:8px 0 18px}.badges,.links,.controls,.frame-meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.badge{font-size:12px;background:#fff;border:1px solid #d5deeb;border-radius:100px;padding:5px 10px}.links{font-size:12px;gap:18px;margin-bottom:22px}.grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px;align-items:start}.card{background:#fff;border:1px solid #d5deeb;border-radius:14px;overflow:hidden;box-shadow:0 6px 22px #1e355508}.canvas{background:#f8fafc;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center}.canvas svg{display:block;width:100%;height:auto;max-height:100%}.controls{padding:14px;border-top:1px solid #e0e6ef}.controls .primary{background:#245fa9;border-color:#245fa9;color:#fff;min-width:100px}.controls .primary:hover:not(:disabled){background:#174c8d}.speed{display:flex;gap:7px;align-items:center;color:#55647b;font-size:12px}.overview-toggle{font-size:12px;display:flex;align-items:center;gap:5px;white-space:nowrap}.scrubber{display:flex;gap:12px;align-items:center;padding:0 16px 15px}.scrubber input{width:100%;accent-color:#245fa9}.scrubber output{font-variant-numeric:tabular-nums;white-space:nowrap;font-size:12px;color:#55647b;min-width:65px;text-align:right}.frame-info{padding:16px;border-top:1px solid #e0e6ef}.frame-info h2{font-size:16px;margin:0 0 7px}.frame-info p{font-size:13px;line-height:1.6;color:#55647b;margin:0 0 10px;white-space:pre-wrap}.frame-meta{font-size:11px;color:#66758a;gap:5px 14px;overflow-wrap:anywhere}.steps h2{font-size:13px;margin:0;padding:17px;border-bottom:1px solid #e0e6ef}.steps ol{list-style:none;counter-reset:step;padding:7px;margin:0;max-height:720px;overflow:auto}.steps li{counter-increment:step;margin:3px 0}.steps button{width:100%;display:flex;gap:9px;text-align:left;border:1px solid transparent;background:transparent;padding:9px 7px;font-size:12px;line-height:1.4}.steps button:before{content:counter(step);flex:0 0 22px;width:22px;height:22px;display:grid;place-items:center;border-radius:50%;background:#edf1f7;color:#65758e;font-size:10px;font-variant-numeric:tabular-nums}.steps button[aria-current="step"]{background:#edf4ff;border-color:#c8dbf6;color:#174c8d}.steps button[aria-current="step"]:before{background:#245fa9;color:white}.step-label{padding-top:2px}.provenance{margin-top:16px;font-size:12px;line-height:1.6;padding:15px 18px}.provenance summary{cursor:pointer;font-weight:650}.provenance dl{display:grid;grid-template-columns:160px minmax(0,1fr);gap:8px 14px;margin:17px 0 0}.provenance dt{color:#66758a}.provenance dd{margin:0;overflow-wrap:anywhere;white-space:pre-wrap}.provenance code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}.footnote{font-size:11px;color:#66758a;margin:14px 0 0;line-height:1.6}.error{padding:24px;color:#a52a2a;font-size:14px}
    @media(max-width:1000px){.grid{grid-template-columns:minmax(0,1fr)}.steps ol{max-height:260px}.page{padding:16px}.controls{gap:7px}.controls button{font-size:12px}.provenance dl{grid-template-columns:1fr;gap:2px}.provenance dd{margin-bottom:10px}}
    @media print{body{background:white}.page{padding:0;max-width:none}.controls,.scrubber,.steps,.links,.provenance{display:none}.grid{display:block}.card{box-shadow:none;border:0}.intro{font-size:11px}.frame-info{padding:8px 0}.canvas{break-inside:avoid}.footnote{font-size:9px}}
  </style>
</head>
<body>
<main class="page">
  <p class="eyebrow">Ariadne · logística v2 · evidência registrada</p>
  <h1>${escapeHTML(title)}</h1>
  <div class="badges"><span class="badge">${escapeHTML(row.execution_kind || 'Tipo não informado')}</span><span class="badge">${escapeHTML(row.model || 'Sem modelo real informado')}</span><span class="badge">Repetição ${escapeHTML(row.repetition ?? 1)}</span><span class="badge">${scene.frames.length} quadros</span></div>
  <p class="intro">Sequência didática reconstruída dos registros do episódio. O ritmo da reprodução não representa duração, simultaneidade ou mensagens diretas entre agentes. Os vínculos apresentados passam pelo orquestrador; cada quadro mantém seus identificadores de origem.</p>
  <nav class="links" aria-label="Arquivos exportados"><a href="overview.svg" download>SVG geral</a><a href="episode.json" download>Episódio JSON</a><a href="frames.json" download>Quadros JSON</a><a href="provenance.json" download>Proveniência JSON</a></nav>
  <div class="grid">
    <section class="card" aria-label="Reprodução do fluxo">
      <div class="canvas" id="flow-canvas" role="img" aria-label="Diagrama do quadro atual"><noscript>Ative JavaScript para reproduzir o fluxo. O arquivo overview.svg contém a visão geral estática.</noscript></div>
      <div class="controls">
        <button type="button" id="previous" aria-label="Quadro anterior">← Anterior</button>
        <button type="button" id="play" class="primary">Reproduzir</button>
        <button type="button" id="next" aria-label="Próximo quadro">Próximo →</button>
        <label class="speed">Ritmo <select id="speed"><option value="900">Rápido · 0,9 s</option><option value="1800" selected>Normal · 1,8 s</option><option value="3200">Lento · 3,2 s</option></select></label>
        <label class="overview-toggle"><input type="checkbox" id="overview">Visão geral</label>
        <button type="button" id="download">Baixar SVG atual</button>
      </div>
      <div class="scrubber"><input type="range" id="position" min="0" max="${scene.frames.length - 1}" step="1" value="0" aria-label="Selecionar quadro"><output id="progress" for="position">1 / ${scene.frames.length}</output></div>
      <div class="frame-info"><h2 id="frame-title"></h2><p id="frame-text"></p><div class="frame-meta" id="frame-meta"></div></div>
    </section>
    <aside class="card steps" aria-label="Ordem dos quadros"><h2>Sequência de apresentação</h2><ol id="frame-list"></ol></aside>
  </div>
  <details class="card provenance"><summary>Origem e identificação do episódio</summary><dl>
    <dt>Arquivo de origem</dt><dd><code>${escapeHTML(provenance.source_path)}</code></dd>
    <dt>SHA-256 da origem</dt><dd><code>${escapeHTML(provenance.source_sha256)}</code></dd>
    <dt>SHA-256 do episódio</dt><dd><code>${escapeHTML(provenance.episode_sha256)}</code></dd>
    <dt>Trace ID</dt><dd><code>${escapeHTML(provenance.selection.trace_id || 'Não registrado')}</code></dd>
    <dt>Task IDs</dt><dd><code>${escapeHTML(provenance.task_ids.join('\n') || 'Não registrados')}</code></dd>
    <dt>Workflow IDs</dt><dd><code>${escapeHTML(provenance.workflow_ids.join('\n') || 'Não registrados')}</code></dd>
    <dt>Exportação</dt><dd>${escapeHTML(provenance.generated_at)}</dd>
  </dl></details>
  <p class="footnote">← / →: avançar ou voltar · Espaço: reproduzir ou pausar · Home / End: primeiro ou último quadro. A apresentação é uma leitura dos dados preservados, sem novas chamadas de modelo ou execução de ações.</p>
</main>
<script type="module">
${inlineModule}

{
  const exportedScene = ${scriptJSON(scene)};
  const canvas = document.getElementById('flow-canvas');
  const previous = document.getElementById('previous');
  const next = document.getElementById('next');
  const play = document.getElementById('play');
  const speed = document.getElementById('speed');
  const position = document.getElementById('position');
  const progress = document.getElementById('progress');
  const overview = document.getElementById('overview');
  const frameTitle = document.getElementById('frame-title');
  const frameText = document.getElementById('frame-text');
  const frameMeta = document.getElementById('frame-meta');
  const frameList = document.getElementById('frame-list');
  let currentIndex = 0;
  let interval = null;
  let currentSVG = '';
  const frameButtons = exportedScene.frames.map((frame, index) => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    const label = document.createElement('span');
    label.className = 'step-label';
    label.textContent = frame.title || frame.kind || 'Quadro ' + (index + 1);
    button.append(label);
    button.addEventListener('click', () => { stop(); overview.checked = false; show(index); });
    item.append(button);
    frameList.append(item);
    return button;
  });

  function show(index) {
    currentIndex = Math.max(0, Math.min(index, exportedScene.frames.length - 1));
    const visibleIndex = overview.checked ? exportedScene.frames.length - 1 : currentIndex;
    const frame = exportedScene.frames[visibleIndex];
    currentSVG = renderFlowSVG(exportedScene, visibleIndex, { overview: overview.checked, animate: interval !== null });
    canvas.innerHTML = currentSVG;
    canvas.setAttribute('aria-label', overview.checked ? 'Visão geral do episódio' : frame.title || 'Quadro atual');
    frameTitle.textContent = overview.checked ? 'Visão geral do episódio' : frame.title || 'Quadro ' + (currentIndex + 1);
    frameText.textContent = overview.checked ? 'Todos os vínculos desta observação, reconstruídos dos registros. Selecione um quadro para acompanhar a sequência.' : frame.text || '';
    frameMeta.replaceChildren();
    for (const [label, value] of [['Papel', frame.role], ['Tipo', frame.kind], ['Ciclo', frame.cycle], ['Task', frame.task_id], ['Workflow', frame.workflow_id], ['Histórico', frame.history_index]]) {
      if (value === undefined || value === null || value === '') continue;
      const metadata = document.createElement('span');
      metadata.textContent = label + ': ' + value;
      frameMeta.append(metadata);
    }
    position.value = currentIndex;
    position.disabled = overview.checked;
    progress.textContent = overview.checked ? 'Visão geral' : (currentIndex + 1) + ' / ' + exportedScene.frames.length;
    previous.disabled = overview.checked || currentIndex === 0;
    next.disabled = overview.checked || currentIndex === exportedScene.frames.length - 1;
    play.disabled = overview.checked;
    for (let index = 0; index < frameButtons.length; index += 1) {
      if (!overview.checked && index === currentIndex) frameButtons[index].setAttribute('aria-current', 'step');
      else frameButtons[index].removeAttribute('aria-current');
    }
  }

  function stop() {
    if (interval !== null) clearInterval(interval);
    interval = null;
    play.textContent = 'Reproduzir';
    play.setAttribute('aria-pressed', 'false');
  }

  function start() {
    stop();
    if (currentIndex === exportedScene.frames.length - 1) currentIndex = 0;
    interval = setInterval(() => {
      if (currentIndex < exportedScene.frames.length - 1) show(currentIndex + 1);
      if (currentIndex === exportedScene.frames.length - 1) { stop(); show(currentIndex); }
    }, Number(speed.value));
    play.textContent = 'Pausar';
    play.setAttribute('aria-pressed', 'true');
    show(currentIndex);
  }

  previous.addEventListener('click', () => { stop(); show(currentIndex - 1); });
  next.addEventListener('click', () => { stop(); show(currentIndex + 1); });
  play.addEventListener('click', () => { if (interval === null) start(); else { stop(); show(currentIndex); } });
  speed.addEventListener('change', () => { if (interval !== null) start(); });
  position.addEventListener('input', () => { stop(); show(Number(position.value)); });
  overview.addEventListener('change', () => { stop(); show(currentIndex); });
  document.getElementById('download').addEventListener('click', () => {
    const blobURL = URL.createObjectURL(new Blob([currentSVG], { type: 'image/svg+xml;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = blobURL;
    const stem = (exportedScene.row.case + '-' + exportedScene.row.configuration).replace(/[^a-zA-Z0-9_-]/g, '-');
    link.download = stem + (overview.checked ? '-overview' : '-frame-' + String(currentIndex + 1).padStart(3, '0')) + '.svg';
    link.click();
    setTimeout(() => URL.revokeObjectURL(blobURL), 1000);
  });
  document.addEventListener('keydown', (event) => {
    if (event.target.closest('input,select,textarea,button') || event.altKey || event.ctrlKey || event.metaKey) return;
    if (!['ArrowLeft', 'ArrowRight', ' ', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    overview.checked = false;
    if (event.key === ' ') { if (interval === null) start(); else { stop(); show(currentIndex); } return; }
    stop();
    show(event.key === 'Home' ? 0 : event.key === 'End' ? exportedScene.frames.length - 1 : currentIndex + (event.key === 'ArrowLeft' ? -1 : 1));
  });
  window.addEventListener('pagehide', stop);
  try { show(0); } catch (error) { canvas.classList.add('error'); canvas.textContent = 'Não foi possível apresentar os registros: ' + error.message; console.error(error); }
}
</script>
</body>
</html>
`;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) { process.stdout.write(USAGE); return; }
  const sourcePath = path.resolve(options.input);
  const outputPath = path.resolve(options.output);
  // Read once: all exports and the source digest refer to these exact bytes.
  const sourceBytes = await readFile(sourcePath);
  const document = JSON.parse(sourceBytes.toString('utf8'));
  if (!Array.isArray(document)) throw new Error('O arquivo de entrada deve conter um array de observações.');
  const candidates = document.filter((row) => row && row.case === options.case && row.configuration === options.configuration && Number(row.repetition ?? 1) === options.repetition);
  if (candidates.length !== 1) {
    throw new Error(`A seleção encontrou ${candidates.length} observações; é necessário exatamente uma para ${options.case} / ${options.configuration} / repetição ${options.repetition}.`);
  }
  const row = candidates[0];
  const episodeJSON = json(row);
  const moduleSource = await readFile(MODULE_PATH, 'utf8');
  // The renderer is a pure ESM file. A data URL also works in packages that do
  // not declare "type": "module", without changing the Inspector's package.
  const renderer = await import(`data:text/javascript;base64,${Buffer.from(moduleSource).toString('base64')}`);
  if (typeof renderer.createFlowScene !== 'function' || typeof renderer.renderFlowSVG !== 'function') {
    throw new Error('O módulo de fluxo deve exportar createFlowScene e renderFlowSVG.');
  }
  const scene = renderer.createFlowScene(structuredClone(row));
  if (!scene || !Array.isArray(scene.frames) || !scene.frames.length) throw new Error('O episódio não produziu quadros de apresentação.');
  if (!scene.row) scene.row = structuredClone(row);
  const overviewSVG = renderer.renderFlowSVG(scene, scene.frames.length - 1, { overview: true });
  if (typeof overviewSVG !== 'string' || !/<svg\b/.test(overviewSVG)) throw new Error('O renderizador não produziu um SVG válido.');
  const provenance = {
    schema_version: 1,
    generator: 'tools/inspector/scripts/export-logistics-flow.mjs',
    generated_at: new Date().toISOString(),
    source_path: sourcePath,
    source_sha256: sha256(sourceBytes),
    episode_sha256: sha256(episodeJSON),
    renderer_path: MODULE_PATH,
    renderer_sha256: sha256(moduleSource),
    source_observation_index: document.indexOf(row),
    selection: {
      case: row.case,
      configuration: row.configuration,
      repetition: Number(row.repetition ?? 1),
      execution_kind: row.execution_kind ?? null,
      model: row.model ?? null,
      trace_id: row.trace_id ?? null,
    },
    task_ids: unique((row.calls || []).map((call) => call.task_id)),
    workflow_ids: unique((row.workflows || []).map((workflow) => workflow.workflow_id)),
    workflow_run_ids: unique((row.workflows || []).map((workflow) => workflow.run_id)),
    workflow_trace_ids: unique((row.workflows || []).map((workflow) => workflow.trace_id)),
    frame_count: scene.frames.length,
    presentation_semantics: 'Sequência didática dos registros; os intervalos de reprodução não representam duração, simultaneidade ou mensagens diretas entre agentes.',
  };
  const files = new Map([
    ['episode.json', episodeJSON],
    ['frames.json', json(scene.frames)],
    ['provenance.json', json(provenance)],
    ['overview.svg', `${overviewSVG.trim()}\n`],
    ['flow.html', createHTML(scene, provenance, moduleSource)],
  ]);
  const incidentIndex = scene.frames.findIndex(frame => frame.kind === 'incident');
  const recoveryIndex = scene.frames.findIndex(frame => frame.kind === 'effect' && frame.text.startsWith('TRANSFER'));
  for (const [name, index] of [['incident.svg', incidentIndex], ['recovery.svg', recoveryIndex]]) {
    if (index >= 0) files.set(name, `${renderer.renderFlowSVG(scene, index).trim()}\n`);
  }
  await mkdir(outputPath, { recursive: true });
  for (const [name, contents] of files) await writeFile(path.join(outputPath, name), contents, 'utf8');
  process.stdout.write(json({ output: outputPath, case: row.case, configuration: row.configuration, repetition: provenance.selection.repetition, frames: scene.frames.length, source_sha256: provenance.source_sha256, files: [...files.keys()] }));
}

main().catch((error) => {
  process.stderr.write(`Falha na exportação: ${error.message}\n`);
  process.exitCode = 1;
});
