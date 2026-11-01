"""Player HTML do incêndio: a grade dia a dia, drones, ordens, rádio e ações.

    python -m studies.scenarios.wildfire.player <execução ou mission-result.json> [outra] --output player.html
    python -m studies.scenarios.wildfire.player --output player.html        # sem dados: abre arquivos no navegador

Gera uma página autônoma (sem dependências externas) que reconstrói o
mundo a partir do ``mission-result.json`` do contrato: o estado inicial vem
do pedido da missão (ou do payload do primeiro ``PlannerRequest``) e cada
rodada PLAN acrescenta ``context_after.state``, as ações aplicadas pelo
mundo, as decisões dos drones BDI, as ordens e crenças do comandante (ou as
ações do piloto) e o rádio. Com duas missões, mostra-as lado a lado,
sincronizadas pelo dia (cada tique do mundo aparece como um dia). O catálogo
de casos vai embutido para desenhar as estruturas e bases que só o rádio
anunciou, a partir do dia do anúncio. O rádio fica no alto da página, um
aviso por vez, porque é a informação que o modelo precisa interpretar.

``analysis.py`` chama ``player_html`` para gravar um player por caso; a
página sem dados embutidos abre qualquer ``mission-result.json`` pelo botão
ou arrastando o arquivo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from studies.scenarios.wildfire.domain.cases import CASES
from studies.scenarios.wildfire.mission import LABELS

KEEP_STEP_RESULT = ('step_id', 'status')
KEEP_OUTPUT_META = ('selected_plan', 'provider', 'model', 'latency_ms', 'usage', 'shortcut', 'fallback')


def compact_document(document):
    """Só o que o player lê: estados por rodada, saídas dos passos, ordens e metadados."""
    compact = {key: document.get(key) for key in ('mission_id', 'status', 'created_at', 'completed_at', 'error') if key in document}
    request = document.get('request') or {}
    context = request.get('context') or {}
    if not context:
        first = (document.get('rounds') or [{}])[0]
        context = ((first.get('planner_task') or {}).get('payload') or {}).get('context') or {}
    compact['request'] = {'context': {'state': context.get('state'), 'case': context.get('case')},
                          'metadata': request.get('metadata') or {}}
    rounds = []
    for item in document.get('rounds') or []:
        planner_result = item.get('planner_result') or {}
        output = planner_result.get('output') or {}
        rounds.append({
            'round': item.get('round'), 'action': item.get('action'), 'planner_summary': item.get('planner_summary', ''),
            'started_at': item.get('started_at'), 'completed_at': item.get('completed_at'),
            'planner_result': {'metadata': {k: v for k, v in (planner_result.get('metadata') or {}).items() if k in KEEP_OUTPUT_META},
                               'output': {'context_update': output.get('context_update') or {}, 'summary': output.get('summary', '')}},
            'result': {'status': (item.get('result') or {}).get('status'),
                       'step_results': [{**{k: step.get(k) for k in KEEP_STEP_RESULT},
                                         'result': {'agent_id': (step.get('result') or {}).get('agent_id'),
                                                    'output': (step.get('result') or {}).get('output') or {},
                                                    'metadata': {k: v for k, v in ((step.get('result') or {}).get('metadata') or {}).items()
                                                                 if k in KEEP_OUTPUT_META}},
                                         'task': {'attempt': (step.get('task') or {}).get('attempt')}}
                                        for step in (item.get('result') or {}).get('step_results', [])]},
            'context_after': {'state': (item.get('context_after') or {}).get('state')},
        })
    compact['rounds'] = rounds
    return compact


def load_document(path):
    path = Path(path)
    if path.is_dir():
        path = path / 'mission-result.json'
    return json.loads(path.read_text(encoding='utf-8'))


def mission_entry(document, *, label=None, configuration=None):
    metadata = (document.get('request') or {}).get('metadata') or {}
    configuration = configuration or metadata.get('configuration') or ''
    return {'label': label or LABELS.get(configuration, configuration or 'missão'), 'configuration': configuration,
            'document': compact_document(document)}


def player_html(missions=(), *, title='Incêndio florestal'):
    catalog = {case['id']: case for case in CASES}
    labels = dict(LABELS)
    return (TEMPLATE.replace('__TITLE__', json.dumps(title, ensure_ascii=False))
            .replace('__CATALOG__', json.dumps(catalog, ensure_ascii=False))
            .replace('__LABELS__', json.dumps(labels, ensure_ascii=False))
            .replace('__MISSIONS__', json.dumps(list(missions), ensure_ascii=False).replace('</', '<\\/')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inputs', nargs='*', type=Path, help='até duas execuções (pasta) ou mission-result.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--title', default='Incêndio florestal')
    args = parser.parse_args(argv)
    if len(args.inputs) > 2:
        parser.error('at most two missions side by side')
    missions = [mission_entry(load_document(path)) for path in args.inputs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(player_html(missions, title=args.title), encoding='utf-8')
    print(f'Player: {args.output}')
    return 0


TEMPLATE = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wildfire Player</title>
<style>
:root { --bg:#f6f5f1; --card:#ffffff; --ink:#1b1b1b; --muted:#5e5d58; --line:#e1dfd8; --accent:#2a78d6; --accent2:#eb6834;
  --veg:#dfeedb; --ash:#4a4a4a; --obst:#1e1e1e; --base:#2a78d6; --basedead:#9aa5b1; --struct:#8e44ad; --f1:#f6b26b; --f2:#e8742f; --f3:#c0392b; --ok:#1baf7a; --bad:#e34948; --drop:#1e90ff; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#15161a; --card:#1f2026; --ink:#f0efe9; --muted:#a8a69e; --line:#34353d; --veg:#2f4a2e; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.45 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
header { padding:14px 20px 8px; display:flex; flex-wrap:wrap; gap:12px; align-items:baseline; }
header h1 { font-size:18px; margin:0; }
header .sub { color:var(--muted); }
.topbar { position:sticky; top:0; background:var(--bg); z-index:2; border-bottom:1px solid var(--line); }
.controls { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; padding:6px 20px 8px; }
button, select, input[type=file] { font:inherit; }
button { border:1px solid var(--line); background:var(--card); color:var(--ink); border-radius:8px; padding:5px 11px; cursor:pointer; }
button:hover { border-color:var(--accent); }
button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
input[type=range] { width:min(420px, 60vw); }
.tick { font-variant-numeric:tabular-nums; min-width:11ch; font-weight:600; }
.radioband { display:flex; gap:10px; align-items:flex-start; padding:8px 20px 10px; border-top:1px dashed var(--line); }
.radioband .rlabel { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); padding-top:7px; white-space:nowrap; }
.radioband .rbody { flex:1; display:grid; gap:4px; }
.radioband .msg { padding:7px 10px; border-radius:8px; background:var(--card); border:1px solid var(--line); font-size:13.5px; }
.radioband .msg.new { border-color:var(--accent2); box-shadow:0 0 0 2px color-mix(in srgb, var(--accent2) 35%, transparent); }
.radioband .msg.old { color:var(--muted); }
.radioband .msg b { color:var(--accent2); }
.radioband .msg.old b { color:var(--muted); }
.radioband details { font-size:12px; color:var(--muted); }
.radioband details .msg { margin-top:4px; }
.radioband summary { cursor:pointer; white-space:nowrap; padding-top:7px; }
main { display:grid; gap:16px; padding:16px 20px; grid-template-columns:repeat(auto-fit, minmax(460px, 1fr)); }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; display:grid; gap:10px; align-content:start; }
.card h2 { margin:0; font-size:15px; display:flex; justify-content:space-between; gap:8px; align-items:baseline; }
.card h2 .cfg { font-size:12px; color:var(--muted); font-weight:500; }
canvas { width:100%; max-width:520px; justify-self:center; image-rendering:pixelated; border:1px solid var(--line); border-radius:6px; background:var(--veg); cursor:crosshair; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { border:1px solid var(--line); border-radius:999px; padding:2px 10px; font-size:12px; color:var(--muted); }
.chip b { color:var(--ink); font-variant-numeric:tabular-nums; }
.chip.bad b { color:var(--bad); }
.delta { font-size:13px; padding:6px 10px; border-radius:8px; background:var(--bg); }
.delta b { font-weight:600; }
.box { border-top:1px solid var(--line); padding-top:8px; }
.box h3 { margin:0 0 4px; font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }
table { width:100%; border-collapse:collapse; font-size:12.5px; }
th, td { text-align:left; padding:3px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.st-applied { color:var(--ok); } .st-rejected { color:var(--bad); font-weight:600; } .st-idle { color:var(--muted); }
.summary { font-size:13px; color:var(--ink); }
.meta { color:var(--muted); font-size:12px; }
code { font-size:11.5px; color:var(--muted); }
.legend { display:grid; gap:4px; font-size:12px; color:var(--muted); }
.legend .row { display:flex; flex-wrap:wrap; gap:4px 12px; align-items:center; }
.legend .row > b { color:var(--ink); font-weight:600; min-width:7ch; }
.legend .li { display:inline-flex; align-items:center; gap:5px; }
.legend .sw { display:inline-block; width:12px; height:12px; border-radius:2px; background:var(--c); }
.legend svg { width:16px; height:16px; }
.chart { width:100%; height:150px; }
.drop { border:2px dashed var(--line); border-radius:12px; padding:30px; text-align:center; color:var(--muted); margin:20px; }
.drop.over { border-color:var(--accent); }
.tip { position:absolute; pointer-events:none; background:var(--ink); color:var(--bg); font-size:12px; padding:6px 9px; border-radius:6px; z-index:5; max-width:260px; line-height:1.35; }
footer { color:var(--muted); font-size:12px; padding:10px 20px 24px; max-width:1100px; }
.hidden { display:none !important; }
</style>
</head>
<body>
<header>
  <h1 id="title"></h1>
  <span class="sub" id="subtitle"></span>
</header>
<div class="topbar">
<div class="controls">
  <button id="first" title="início (Home)">⏮</button>
  <button id="prev" title="dia anterior (←)">◀</button>
  <button id="play" class="primary" title="reproduzir/pausar (espaço)">▶ Reproduzir</button>
  <button id="next" title="próximo dia (→)">▶</button>
  <button id="last" title="fim (End)">⏭</button>
  <input id="slider" type="range" min="0" max="0" value="0">
  <span class="tick" id="ticklabel">Dia 0 de 0</span>
  <label>velocidade <select id="speed"><option value="1400">0,5×</option><option value="700" selected>1×</option><option value="350">2×</option><option value="170">4×</option></select></label>
  <label><input type="checkbox" id="trails" checked> rastros</label>
  <span style="flex:1"></span>
  <label class="meta">abrir <input type="file" id="file" accept=".json" multiple></label>
  <button id="clear" class="hidden">limpar</button>
</div>
<div class="radioband" id="radioband"></div>
</div>
<div class="drop" id="drop">Arraste um ou dois <code>mission-result.json</code> aqui, ou use "abrir" acima. Dois arquivos aparecem lado a lado, sincronizados pelo dia.</div>
<main id="main"></main>
<div id="tip" class="tip hidden"></div>
<footer><b>Como ler.</b> Cada dia é uma rodada da missão: o modelo (comandante ou piloto) decide, os drones agem, o fogo avança. O rádio no alto é o que chegou ao modelo naquele dia; parte da verdade do mundo só existe nessas mensagens. Em cada painel: a grade (drones <code>d1…</code>, bases <code>B1…</code>, passe o mouse sobre uma célula para detalhes), o que mudou no dia, o resumo e as ordens do comandante ou as ações do piloto, e por drone a decisão tomada e a resposta do mundo. Tudo vem do <code>mission-result.json</code> do contrato; bases e estruturas que só o rádio anunciou são desenhadas a partir do catálogo de casos, no dia do anúncio.</footer>
<script>
const TITLE = __TITLE__;
const CATALOG = __CATALOG__;
const LABELS = __LABELS__;
const EMBEDDED = __MISSIONS__;

// ---------------------------------------------------------------- vocabulário em português
const PT = {
  action: { move: 'voar para', drop: 'gota em', resupply: 'reabastecer', hold: 'manter posição' },
  plan: { stand_down: 'fora de combate', hold_ordered: 'manter posição (ordem)', resupply_here: 'reabastecer aqui', return_to_base: 'voltar à base',
          attack_target: 'atacar o alvo ordenado', guard_target: 'guardar o alvo', attack_nearest: 'atacar o foco mais próximo',
          hold_position: 'manter posição (sem alvo seguro)', shortest_path: 'caminho mais curto' },
  objective: { auto: 'livre (o drone decide)', attack: 'atacar', protect: 'proteger', resupply: 'reabastecer', return: 'voltar à base', hold: 'manter posição' },
  status: { applied: 'aplicada', rejected: 'rejeitada', idle: 'ociosa' },
  condition: { ok: 'ok', lost: 'perdido', offline: 'fora do ar' },
  mission: { MISSION_STATUS_COMPLETED: 'concluída', MISSION_STATUS_FAILED: 'falhou', MISSION_STATUS_ABORTED: 'abortada' },
  dir: { N: 'norte', S: 'sul', E: 'leste', W: 'oeste' }, arrow: { N: '↑', S: '↓', E: '→', W: '←' },
};
const pt = (table, key) => (PT[table] && PT[table][key]) || key || '';

// ---------------------------------------------------------------- extração
function coords(c) { const [x, y] = String(c).split(','); return [parseInt(x, 10), parseInt(y, 10)]; }

function extract(doc, label, configuration) {
  const rounds = doc.rounds || [];
  const req = doc.request || {};
  let context = (req.context && req.context.state) ? req.context : null;
  if (!context && rounds.length) {
    const p = rounds[0].planner_task && rounds[0].planner_task.payload;
    context = p && p.context ? p.context : null;
  }
  if (!context || !context.state) throw new Error('mission-result sem estado inicial');
  const caseRef = context.case || {};
  const info = CATALOG[caseRef.id] || null;
  const meta = req.metadata || {};
  configuration = configuration || meta.configuration || '';
  label = label || LABELS[configuration] || configuration || 'missão';
  const ticks = [{ tick: Number(context.state.tick || 0), state: context.state, actions: [], decisions: {}, orders: {}, beliefs: null,
                   summary: 'estado inicial', planner: null, round: 0, lost: [] }];
  let cumCalls = 0, cumTokens = 0, cumRejected = 0, model = null;
  for (const r of rounds) {
    const pr = r.planner_result || {};
    const pm = pr.metadata || {};
    const isModel = pm.provider === 'openai' || pm.provider === 'deterministic-integration-substitute';
    if (isModel) cumCalls += 1;
    if (pm.provider === 'openai' && pm.model) model = pm.model;
    if (pm.usage) cumTokens += Number(pm.usage.input_tokens || 0) + Number(pm.usage.output_tokens || 0);
    if (r.action !== 'PLANNER_ACTION_PLAN') {
      ticks[ticks.length - 1].done = { action: r.action, summary: r.planner_summary || '' };
      continue;
    }
    const state = r.context_after && r.context_after.state;
    if (!state) continue;
    const steps = (r.result && r.result.step_results) || [];
    const world = steps.find(s => s.step_id === 'world');
    const wo = (world && world.result && world.result.output) || {};
    const decisions = {};
    for (const s of steps) {
      if (s.step_id === 'world') continue;
      const o = (s.result && s.result.output) || {};
      if (o.drone) decisions[o.drone] = { plan: (s.result.metadata || {}).selected_plan || o.plan, action: o.action, target: o.target, reason: o.reason,
                                          agent: s.result.agent_id, attempt: (s.task || {}).attempt || 1, status: s.status };
    }
    const update = ((pr.output || {}).context_update) || {};
    const pilotActions = (update.last_plan && update.last_plan.actions) || null;
    const actions = wo.applied || [];
    cumRejected += actions.filter(a => a.status === 'rejected').length;
    ticks.push({ tick: Number(state.tick), state, actions, decisions, orders: update.orders || {}, beliefs: update.command || null,
                 pilotActions, summary: r.planner_summary || (pr.output || {}).summary || '',
                 planner: { provider: pm.provider, model: pm.model, latency: pm.latency_ms, usage: pm.usage, shortcut: pm.shortcut },
                 round: r.round, lost: wo.lost || [], cum: { calls: cumCalls, tokens: cumTokens, rejected: cumRejected },
                 workflowStatus: r.result && r.result.status });
  }
  ticks[0].cum = { calls: 0, tokens: 0, rejected: 0 };
  return { label, configuration, caseId: caseRef.id, info, ticks, status: doc.status, error: doc.error, model };
}

function truthAt(info, tick) {
  const out = { disabled: new Set(), hidden: {} };
  if (!info) return out;
  for (const ev of info.events || []) {
    if (Number(ev.tick) > tick) continue;
    const fx = ev.effects || {};
    for (const b of fx.disable_bases || []) out.disabled.add(b);
    for (const [c, name] of Object.entries(fx.hidden_structures || {})) out.hidden[c] = name;
  }
  return out;
}

// ---------------------------------------------------------------- desenho
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
function structureLetter(name) { return name && name.toLowerCase().includes('hosp') ? 'H' : 'E'; }

function drawGrid(canvas, mission, index, trails) {
  const t = mission.ticks[index];
  const prev = index > 0 ? mission.ticks[index - 1] : null;
  const st = t.state;
  const W = Number(st.width), H = Number(st.height);
  const size = Math.max(10, Math.floor(520 / Math.max(W, H)));
  canvas.width = W * size; canvas.height = H * size;
  const ctx = canvas.getContext('2d');
  const ash = new Set(st.ash || []), obst = new Set(st.obstacles || []);
  const fires = st.fires || {};
  const truth = truthAt(mission.info, t.tick);
  const fcol = { 1: css('--f1'), 2: css('--f2'), 3: css('--f3') };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const c = x + ',' + y;
    let fill = css('--veg');
    if (obst.has(c)) fill = css('--obst'); else if (ash.has(c)) fill = css('--ash');
    else if (fires[c] !== undefined) fill = fcol[Math.max(1, Math.min(3, Number(fires[c])))];
    ctx.fillStyle = fill; ctx.fillRect(x * size, y * size, size, size);
    ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 0.5; ctx.strokeRect(x * size + 0.25, y * size + 0.25, size - 0.5, size - 0.5);
  }
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  // bases: quadrado azul com o nome (B1, B2...), cinza quando o rádio a tirou de serviço
  for (const [bid, base] of Object.entries(st.bases || {})) {
    const [x, y] = coords(base.at);
    ctx.fillStyle = truth.disabled.has(bid) ? css('--basedead') : css('--base');
    ctx.fillRect(x * size + 1, y * size + 1, size - 2, size - 2);
    ctx.fillStyle = '#fff'; ctx.font = `bold ${Math.floor(size * 0.42)}px sans-serif`;
    ctx.fillText(bid, x * size + size / 2, y * size + size / 2 + 1);
  }
  // estruturas: roxo com H (hospital) ou E (escola); tracejado quando só o rádio a anunciou
  const visible = Object.fromEntries(Object.entries(st.structures || {}).map(([c, s]) => [c, s.name]));
  const structures = Object.assign({}, visible, truth.hidden);
  for (const [c, name] of Object.entries(structures)) {
    const [x, y] = coords(c);
    const announced = !(c in visible);
    ctx.lineWidth = 2; ctx.strokeStyle = css('--struct');
    if (announced) ctx.setLineDash([3, 2]);
    if (ash.has(c)) { ctx.strokeRect(x * size + 2, y * size + 2, size - 4, size - 4); }
    else { ctx.fillStyle = css('--struct'); ctx.fillRect(x * size + 2, y * size + 2, size - 4, size - 4); if (announced) ctx.strokeStyle = '#fff', ctx.strokeRect(x * size + 3, y * size + 3, size - 6, size - 6); }
    ctx.setLineDash([]);
    ctx.fillStyle = ash.has(c) ? css('--struct') : '#fff'; ctx.font = `bold ${Math.floor(size * 0.5)}px sans-serif`;
    ctx.fillText(structureLetter(name), x * size + size / 2, y * size + size / 2 + 1);
  }
  // gotas deste dia: anel azul na célula alvo
  for (const a of t.actions || []) {
    if (a.status !== 'applied' || a.action !== 'drop' || !a.target) continue;
    const [x, y] = coords(a.target);
    ctx.strokeStyle = css('--drop'); ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(x * size + size / 2, y * size + size / 2, size * 0.42, 0, Math.PI * 2); ctx.stroke();
  }
  // rastros e drones: círculo com o nome (d1, d2...), arco verde/amarelo/vermelho = bateria, pontos azuis = água
  const rejected = new Set((t.actions || []).filter(a => a.status === 'rejected').map(a => a.drone));
  const baseCells = new Set(Object.values(st.bases || {}).map(b => b.at));
  const stacked = {};
  for (const [id, d] of Object.entries(st.drones || {})) (stacked[d.at] = stacked[d.at] || []).push(id);
  for (const [id, d] of Object.entries(st.drones || {})) {
    const [x, y] = coords(d.at);
    const cx = x * size + size / 2, cy = y * size + size / 2;
    if (trails && prev && prev.state.drones && prev.state.drones[id]) {
      const [px, py] = coords(prev.state.drones[id].at);
      if (px !== x || py !== y) {
        ctx.strokeStyle = 'rgba(27,27,27,0.55)'; ctx.lineWidth = 2; ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(px * size + size / 2, py * size + size / 2); ctx.lineTo(cx, cy); ctx.stroke(); ctx.setLineDash([]);
      }
    }
    if (d.condition === 'lost') {
      ctx.fillStyle = '#111'; ctx.font = `bold ${Math.floor(size * 0.9)}px sans-serif`; ctx.fillText('×', cx, cy + 1); continue;
    }
    // em cima de uma base o círculo encolhe para a moldura azul (ou cinza) continuar visível
    const r = size * (baseCells.has(d.at) ? 0.31 : 0.38);
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = d.condition === 'offline' ? '#d8d8d8' : '#fff'; ctx.fill();
    ctx.lineWidth = rejected.has(id) ? 2.5 : 1.5; ctx.strokeStyle = rejected.has(id) ? css('--bad') : (d.condition === 'offline' ? '#888' : '#111'); ctx.stroke();
    const frac = Math.max(0, Math.min(1, Number(d.battery) / Number((st.rules || {}).battery_capacity || 40)));
    ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + frac * Math.PI * 2);
    ctx.strokeStyle = frac > 0.5 ? css('--ok') : (frac > 0.25 ? '#e8a317' : css('--bad')); ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#111'; ctx.font = `bold ${Math.floor(size * 0.4)}px sans-serif`; ctx.fillText(id, cx, cy + 1);
    const water = Number(d.water || 0);
    for (let i = 0; i < water; i++) { ctx.fillStyle = css('--drop'); ctx.fillRect(x * size + 2 + i * 3, y * size + size - 4, 2, 2); }
    // vários drones na mesma célula: só o último fica visível, o selo diz quantos são (a dica do mouse lista todos)
    const group = stacked[d.at];
    if (group.length > 1 && group[group.length - 1] === id) {
      ctx.beginPath(); ctx.arc(cx + r * 0.95, cy - r * 0.95, size * 0.24, 0, Math.PI * 2); ctx.fillStyle = '#111'; ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = `bold ${Math.floor(size * 0.34)}px sans-serif`; ctx.fillText('+' + (group.length - 1), cx + r * 0.95, cy - r * 0.95 + 1);
    }
  }
}

// dica ao passar o mouse: o que há naquela célula
function attachTooltip(canvas, mission) {
  const tip = document.getElementById('tip');
  canvas.onmousemove = e => {
    const t = mission.ticks[Math.min(state.index, mission.ticks.length - 1)];
    const st = t.state, W = Number(st.width), H = Number(st.height);
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / rect.width * W), y = Math.floor((e.clientY - rect.top) / rect.height * H);
    if (x < 0 || y < 0 || x >= W || y >= H) { tip.classList.add('hidden'); return; }
    const c = x + ',' + y, parts = [];
    const ash = new Set(st.ash || []), obst = new Set(st.obstacles || []), fires = st.fires || {};
    const truth = truthAt(mission.info, t.tick);
    let terrain = 'vegetação intacta';
    if (obst.has(c)) terrain = 'obstáculo (não queima, não se sobrevoa)'; else if (ash.has(c)) terrain = 'cinzas (queimou, perda permanente)';
    else if (fires[c] !== undefined) terrain = `fogo de intensidade ${fires[c]} (uma gota tira ${(st.rules || {}).drop_power || 3})`;
    parts.push(`<b>célula ${c}</b>: ${terrain}`);
    for (const [bid, base] of Object.entries(st.bases || {})) if (base.at === c) parts.push(`base ${bid}${truth.disabled.has(bid) ? ' (fora de serviço, segundo o rádio)' : ' (ativa: recarrega bateria e água)'}`);
    const s = (st.structures || {})[c]; const hidden = truth.hidden[c];
    if (s) parts.push(`estrutura: ${s.name} (${s.condition === 'burned' ? 'queimada' : 'intacta'})`);
    else if (hidden) parts.push(`estrutura anunciada pelo rádio: ${hidden}${ash.has(c) ? ' (queimada)' : ''}`);
    for (const [id, d] of Object.entries(st.drones || {})) if (d.at === c) parts.push(`drone ${id}: bateria ${d.battery}/${(st.rules || {}).battery_capacity || 40}, água ${d.water}/${(st.rules || {}).water_capacity || 4}, ${pt('condition', d.condition)}`);
    tip.innerHTML = parts.join('<br>');
    tip.style.left = (e.pageX + 14) + 'px'; tip.style.top = (e.pageY + 14) + 'px';
    tip.classList.remove('hidden');
  };
  canvas.onmouseleave = () => tip.classList.add('hidden');
}

function esc(s) { return String(s === undefined || s === null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function fmtAction(a) { return pt('action', a.action) + (a.target ? ' ' + a.target : ''); }
function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }

// o que mudou entre o dia anterior e este
function deltaText(t, prev) {
  if (!prev) return '';
  const acts = t.actions || [];
  const drops = acts.filter(a => a.status === 'applied' && a.action === 'drop').length;
  const fires = t.state.fires || {}, prevFires = prev.state.fires || {};
  const ashNow = new Set(t.state.ash || []), prevAsh = new Set(prev.state.ash || []);
  const out = Object.keys(prevFires).filter(c => fires[c] === undefined && !ashNow.has(c)).length;
  const newAsh = (t.state.ash || []).filter(c => !prevAsh.has(c)).length;
  const newFires = Object.keys(fires).filter(c => prevFires[c] === undefined).length;
  const rejected = acts.filter(a => a.status === 'rejected').length;
  const offline = Object.entries(t.state.drones || {}).filter(([id, d]) => d.condition === 'offline' && (prev.state.drones[id] || {}).condition !== 'offline').map(([id]) => id);
  const parts = [];
  parts.push(drops ? `<b>${plural(drops, 'gota', 'gotas')}</b>${out ? ` (${plural(out, 'foco apagado', 'focos apagados')})` : ''}` : 'nenhuma gota');
  parts.push(newFires ? `o fogo tomou <b>${plural(newFires, 'célula nova', 'células novas')}</b>` : 'o fogo não avançou');
  if (newAsh) parts.push(`<b>${newAsh}</b> ${newAsh === 1 ? 'virou cinzas' : 'viraram cinzas'}`);
  if (rejected) parts.push(`<span class="st-rejected">${plural(rejected, 'ação rejeitada', 'ações rejeitadas')}</span>`);
  if (offline.length) parts.push(`<span class="st-rejected">${offline.join(', ')} ${offline.length === 1 ? 'ficou' : 'ficaram'} fora do ar</span>`);
  if ((t.lost || []).length) parts.push(`<span class="st-rejected">drones perdidos: ${esc(t.lost.join(', '))}</span>`);
  return parts.join(' · ');
}

function legendHtml() {
  const sw = (v, label) => `<span class="li"><span class="sw" style="--c:${v}"></span>${label}</span>`;
  const drone = (fill, stroke, arc, text) => `<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.3" fill="${fill}" stroke="${stroke}" stroke-width="1.3"/>${arc ? `<path d="M8 1.7 A6.3 6.3 0 0 1 14.3 8" fill="none" stroke="${arc}" stroke-width="2"/>` : ''}<text x="8" y="8.6" font-size="6" text-anchor="middle" dominant-baseline="middle" font-weight="bold" fill="#111">${text}</text><rect x="3" y="12.5" width="1.5" height="1.5" fill="var(--drop)"/><rect x="5.5" y="12.5" width="1.5" height="1.5" fill="var(--drop)"/></svg>`;
  const square = (fill, text, dashed) => `<svg viewBox="0 0 16 16"><rect x="1.5" y="1.5" width="13" height="13" rx="1.5" fill="${fill}"${dashed ? ' stroke="#fff" stroke-width="1.5" stroke-dasharray="2.5 1.5"' : ''}/><text x="8" y="8.6" font-size="6.5" text-anchor="middle" dominant-baseline="middle" font-weight="bold" fill="#fff">${text}</text></svg>`;
  return `<div class="row"><b>terreno</b>${sw('var(--veg)', 'vegetação')}${sw('var(--f1)', 'fogo fraco (1)')}${sw('var(--f2)', 'fogo médio (2)')}${sw('var(--f3)', 'fogo forte (3)')}${sw('var(--ash)', 'cinzas')}${sw('var(--obst)', 'obstáculo')}</div>` +
    `<div class="row"><b>drones</b><span class="li">${drone('#fff', '#111', 'var(--ok)', 'd1')} drone d1: o arco é a bateria, os pontos são a água</span><span class="li">${drone('#fff', 'var(--bad)', 'var(--ok)', 'd2')} ação rejeitada pelo mundo</span><span class="li">${drone('#d8d8d8', '#888', '', 'd3')} fora do ar</span><span class="li"><svg viewBox="0 0 16 16"><circle cx="7" cy="9" r="5.5" fill="#fff" stroke="#111" stroke-width="1.3"/><circle cx="12" cy="4" r="3.5" fill="#111"/><text x="12" y="4.4" font-size="5" text-anchor="middle" dominant-baseline="middle" font-weight="bold" fill="#fff">+2</text></svg> mais drones na mesma célula</span><span class="li"><svg viewBox="0 0 16 16"><text x="8" y="9" font-size="14" text-anchor="middle" dominant-baseline="middle" font-weight="bold" fill="#111">×</text></svg> perdido</span><span class="li"><svg viewBox="0 0 16 16"><line x1="1" y1="8" x2="15" y2="8" stroke="#1b1b1b" stroke-width="2" stroke-dasharray="4 3"/></svg> rastro do dia</span><span class="li"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.5" fill="none" stroke="var(--drop)" stroke-width="2.5"/></svg> gota de água</span></div>` +
    `<div class="row"><b>lugares</b><span class="li">${square('var(--base)', 'B1')} base ativa</span><span class="li">${square('var(--basedead)', 'B1')} base fora de serviço</span><span class="li">${square('var(--struct)', 'H')} hospital</span><span class="li">${square('var(--struct)', 'E')} escola</span><span class="li">${square('var(--struct)', 'H', true)} anunciada só pelo rádio</span></div>`;
}

function renderPanels(card, mission, index, beyond) {
  const t = mission.ticks[index];
  const prev = index > 0 ? mission.ticks[index - 1] : null;
  const st = t.state;
  const single = mission.configuration === 'single-llm' || !!t.pilotActions;
  const drones = Object.entries(st.drones || {}).sort((a, b) => parseInt(a[0].slice(1)) - parseInt(b[0].slice(1)));
  const ok = drones.filter(([, d]) => d.condition === 'ok').length, lost = drones.filter(([, d]) => d.condition === 'lost').length, offline = drones.filter(([, d]) => d.condition === 'offline').length;
  const fires = Object.keys(st.fires || {}).length, ash = (st.ash || []).length;
  const truth = truthAt(mission.info, t.tick);
  const ashSet = new Set(st.ash || []);
  const structuresLost = Object.values(st.structures || {}).filter(s => s.condition === 'burned').length + Object.keys(truth.hidden).filter(c => !(st.structures || {})[c] && ashSet.has(c)).length;
  const rejectedNow = (t.actions || []).filter(a => a.status === 'rejected');
  const byDrone = Object.fromEntries((t.actions || []).map(a => [a.drone, a]));
  const wind = st.wind || {};
  card.querySelector('.chips').innerHTML = [
    ['focos ativos', fires], ['células em cinzas', ash], ['estruturas perdidas', structuresLost, structuresLost > 0],
    ['drones ok', ok + '/' + drones.length], ['fora do ar', offline, offline > 0], ['perdidos', lost, lost > 0],
    ['ações rejeitadas (acumulado)', (t.cum || {}).rejected || 0, ((t.cum || {}).rejected || 0) > 0], ['chamadas ao modelo', (t.cum || {}).calls || 0],
    ['tokens', ((t.cum || {}).tokens || 0).toLocaleString('pt-BR')], ['vento', `${pt('arrow', wind.toward)} para o ${pt('dir', wind.toward)}, força ${wind.speed}`],
  ].map(([k, v, bad]) => `<span class="chip${bad ? ' bad' : ''}">${esc(k)} <b>${v}</b></span>`).join('');
  const delta = card.querySelector('.delta');
  if (index === 0) delta.innerHTML = '<b>Dia 0.</b> Situação inicial, antes de qualquer decisão. Avance um dia para ver a primeira rodada.';
  else delta.innerHTML = `<b>Neste dia:</b> ${deltaText(t, prev)}.` + (beyond ? ` <span class="meta">Esta missão encerrou no dia ${t.tick}; o outro painel continua.</span>` : '');
  const planner = t.planner || {};
  const who = single ? 'piloto' : 'comandante';
  let head = '';
  if (index > 0) {
    const source = planner.shortcut ? `sem chamada ao modelo (atalho: ${esc(planner.shortcut)})` : planner.provider === 'openai' ? `modelo ${esc(planner.model)}${planner.latency ? ', ' + Math.round(planner.latency / 100) / 10 + ' s' : ''}${planner.usage ? ', ' + (Number(planner.usage.input_tokens || 0) + Number(planner.usage.output_tokens || 0)).toLocaleString('pt-BR') + ' tokens' : ''}` : planner.provider === 'deterministic-integration-substitute' ? 'substituto determinístico (demo, sem modelo)' : esc(planner.provider || '');
    head = `<div class="summary"><b>Resumo do ${who} no dia ${t.tick}:</b> ${esc(t.summary)}</div><div class="meta">${source}${t.workflowStatus && !/COMPLETED$/.test(t.workflowStatus) ? ' · <span class="st-rejected">' + esc(t.workflowStatus) + '</span>' : ''}</div>`;
  }
  const b = t.beliefs;
  let command = '';
  if (single) {
    if (t.pilotActions) command = `<table><tr><th>drone</th><th>ação ordenada</th><th>motivo dado pelo piloto</th></tr>${t.pilotActions.map(a => `<tr><td>${esc(a.drone)}</td><td>${esc(fmtAction(a))}</td><td class="meta">${esc(a.reason)}</td></tr>`).join('')}</table>`;
  } else if (b || Object.keys(t.orders || {}).length) {
    command = `<div class="meta">o que o comandante entendeu do rádio · bases fora de serviço: <b>${esc((b && b.disabled_bases || []).join(', ') || 'nenhuma')}</b> · células prioritárias: <b>${esc((b && b.priority_cells || []).join(', ') || 'nenhuma')}</b>${b && b.hazards ? ' · ' + esc(b.hazards) : ''}</div>` +
      `<table><tr><th>drone</th><th>objetivo</th><th>alvo</th><th>nota do comandante</th></tr>${Object.entries(t.orders || {}).sort((x, y) => parseInt(x[0].slice(1)) - parseInt(y[0].slice(1))).map(([d, o]) => `<tr><td>${esc(d)}</td><td>${esc(pt('objective', o.objective))}</td><td>${esc(o.target || '')}</td><td class="meta">${esc(o.note)}</td></tr>`).join('')}</table>`;
  }
  card.querySelector('.command').innerHTML = head + (command ? `<div class="box"><h3>${single ? 'Piloto LLM: ações deste dia' : 'Comandante LLM: ordens deste dia'}</h3>${command}</div>` : '') +
    (t.done ? `<div class="meta">Encerramento: ${esc(t.done.action.replace('PLANNER_ACTION_', ''))} — ${esc(t.done.summary)}</div>` : '');
  card.querySelector('.drones').innerHTML = `<table><tr><th>drone</th><th>posição</th><th class="num">bateria</th><th class="num">água</th><th>${single ? 'ação ordenada pelo piloto' : 'o que o drone decidiu (plano BDI)'}</th><th>resposta do mundo</th></tr>` +
    drones.map(([id, d]) => {
      const dec = (t.decisions || {})[id]; const act = byDrone[id];
      const decision = dec ? `${esc(fmtAction(dec))} <span class="meta">· ${esc(pt('plan', dec.plan))} <code>${esc(dec.plan)}</code>${dec.attempt > 1 ? ', tentativa ' + dec.attempt : ''}</span><br><span class="meta">${esc(dec.reason)}</span>` : (act && act.action ? esc(fmtAction(act)) : '');
      const status = act ? `<span class="st-${esc(act.status)}">${esc(pt('status', act.status))}</span>${act.reason && act.status !== 'applied' ? '<br><span class="meta">' + esc(act.reason) + '</span>' : ''}${act.moved_to ? '<br><span class="meta">chegou a ' + esc(act.moved_to) + (act.arrived ? ' (no alvo)' : ' (a caminho)') + '</span>' : ''}${act.extinguished ? '<br><span class="meta st-applied">apagou o foco</span>' : (act.action === 'drop' && act.status === 'applied' && act.intensity_after !== undefined ? '<br><span class="meta">fogo cai para ' + esc(act.intensity_after) + '</span>' : '')}` : '';
      return `<tr><td>${esc(id)}${d.condition !== 'ok' ? ' <span class="st-rejected">' + esc(pt('condition', d.condition)) + '</span>' : ''}</td><td>${esc(d.at)}</td><td class="num">${esc(d.battery)}</td><td class="num">${esc(d.water)}</td><td>${decision}</td><td>${status}</td></tr>`;
    }).join('') + `</table>` + (rejectedNow.length ? `<div class="meta st-rejected">${rejectedNow.length} ação(ões) rejeitada(s) neste dia.</div>` : '');
  drawChart(card.querySelector('.chart'), mission, index);
}

function drawChart(svg, mission, index) {
  const w = 460, h = 150, l = 36, r = 8, top = 8, bottom = 22;
  const ticks = mission.ticks;
  const maxT = Math.max(1, ticks[ticks.length - 1].tick);
  const burned = ticks.map(t => (t.state.ash || []).length), burning = ticks.map(t => Object.keys(t.state.fires || {}).length);
  const maxY = Math.max(1, ...burned, ...burning);
  const x = t => l + (t / maxT) * (w - l - r), y = v => h - bottom - (v / maxY) * (h - top - bottom);
  const line = (vals, color, width) => `<polyline fill="none" stroke="${color}" stroke-width="${width}" points="${ticks.map((t, i) => x(t.tick) + ',' + y(vals[i])).join(' ')}"/>`;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.innerHTML = `<line x1="${l}" y1="${y(0)}" x2="${w - r}" y2="${y(0)}" stroke="${css('--line')}"/>` +
    line(burned, css('--ash'), 2.5) + line(burning, css('--f2'), 2) +
    `<line x1="${x(ticks[index].tick)}" y1="${top}" x2="${x(ticks[index].tick)}" y2="${h - bottom}" stroke="${css('--accent')}" stroke-dasharray="3 3"/>` +
    `<text x="${l}" y="${h - 6}" font-size="10" fill="${css('--muted')}">dia 0</text><text x="${w - r}" y="${h - 6}" font-size="10" text-anchor="end" fill="${css('--muted')}">dia ${maxT}</text>` +
    `<text x="${l - 4}" y="${y(maxY) + 4}" font-size="10" text-anchor="end" fill="${css('--muted')}">${maxY}</text>` +
    `<text x="${w - r}" y="${top + 10}" font-size="10" text-anchor="end" fill="${css('--ash')}">cinzas ${burned[index]}</text><text x="${w - r}" y="${top + 22}" font-size="10" text-anchor="end" fill="${css('--f2')}">focos ${burning[index]}</text>`;
}

// ---------------------------------------------------------------- rádio no alto: um aviso por vez
function renderRadio() {
  const band = $('radioband');
  if (!state.missions.length) { band.innerHTML = ''; return; }
  const seen = new Map();
  for (const m of state.missions) {
    const idx = Math.min(state.index, m.ticks.length - 1);
    for (const msg of (m.ticks[idx].state.radio || [])) seen.set(msg.tick + '|' + msg.text, msg);
  }
  const all = [...seen.values()].sort((a, b) => Number(a.tick) - Number(b.tick));
  const day = currentDay();
  const now = all.filter(m => Number(m.tick) === day), before = all.filter(m => Number(m.tick) < day);
  let main;
  if (now.length) main = now.map(m => `<div class="msg new"><b>${day === 0 ? 'Briefing inicial' : 'Rádio, dia ' + m.tick}</b> — ${esc(m.text)}</div>`).join('');
  else if (before.length) { const last = before[before.length - 1]; main = `<div class="msg old"><b>Sem novidade no rádio. Último aviso${Number(last.tick) === 0 ? ' foi o briefing inicial' : ' chegou no dia ' + last.tick}</b> — ${esc(last.text)}</div>`; }
  else main = `<div class="msg old">Sem avisos do rádio até o dia ${day}.</div>`;
  const history = all.length > 1 ? `<details${state.radioOpen ? ' open' : ''}><summary>todos os avisos até aqui (${all.length})</summary>${all.map(m => `<div class="msg${Number(m.tick) === day ? ' new' : ''}"><b>${Number(m.tick) === 0 ? 'briefing' : 'dia ' + m.tick}</b> — ${esc(m.text)}</div>`).join('')}</details>` : '';
  band.innerHTML = `<span class="rlabel">📻 rádio</span><div class="rbody">${main}</div>${history}`;
  const details = band.querySelector('details');
  if (details) details.ontoggle = () => { state.radioOpen = details.open; };
}

// ---------------------------------------------------------------- app
const state = { missions: [], index: 0, timer: null, radioOpen: false };
const $ = id => document.getElementById(id);
function currentDay() { if (!state.missions.length) return 0; const m = state.missions[0]; return m.ticks[Math.min(state.index, m.ticks.length - 1)].tick; }
function lastDay() { return Math.max(0, ...state.missions.map(m => m.ticks[m.ticks.length - 1].tick)); }

function buildCards() {
  const main = $('main'); main.innerHTML = '';
  for (const m of state.missions) {
    const card = document.createElement('section'); card.className = 'card';
    card.innerHTML = `<h2><span>${esc(m.label)}</span><span class="cfg">${esc(m.caseId || '')} · ${esc(pt('mission', m.status))}</span></h2>
      <canvas></canvas>
      <div class="legend">${legendHtml()}</div>
      <div class="chips"></div>
      <div class="delta"></div>
      <div class="command box"></div>
      <div class="box"><h3>Drones neste dia</h3><div class="drones"></div></div>
      <div class="box"><h3>Cinzas e focos por dia</h3><svg class="chart"></svg></div>`;
    main.appendChild(card);
    m.card = card;
    attachTooltip(card.querySelector('canvas'), m);
  }
  const maxIndex = Math.max(0, ...state.missions.map(m => m.ticks.length - 1));
  $('slider').max = maxIndex;
  $('drop').classList.toggle('hidden', state.missions.length > 0);
  $('clear').classList.toggle('hidden', state.missions.length === 0 || EMBEDDED.length > 0);
  const first = state.missions[0];
  const model = state.missions.map(m => m.model).find(Boolean);
  $('subtitle').textContent = first && first.info ? `grade ${first.info.width}×${first.info.height} · ${first.info.horizon} dias · ${first.info.drones} drones · ${model ? 'modelo ' + model : 'demo com substitutos determinísticos'}` : '';
}

function render() {
  const trails = $('trails').checked;
  for (const m of state.missions) {
    const idx = Math.min(state.index, m.ticks.length - 1);
    drawGrid(m.card.querySelector('canvas'), m, idx, trails);
    renderPanels(m.card, m, idx, state.index > idx);
  }
  $('slider').value = state.index;
  const maxIndex = Number($('slider').max);
  $('ticklabel').textContent = `Dia ${currentDay()} de ${lastDay()}`;
  renderRadio();
  if (state.index >= maxIndex && state.timer) stop();
}

function go(i) { const max = Number($('slider').max); state.index = Math.max(0, Math.min(max, i)); render(); }
function stop() { if (state.timer) clearInterval(state.timer); state.timer = null; $('play').textContent = '▶ Reproduzir'; }
function play() { if (state.timer) return stop(); if (state.index >= Number($('slider').max)) state.index = 0; $('play').textContent = '⏸ Pausar'; state.timer = setInterval(() => go(state.index + 1), Number($('speed').value)); }

function addDocument(doc, name) {
  try {
    const mission = extract(doc, null, null);
    if (state.missions.length >= 2) state.missions.shift();
    state.missions.push(mission);
    buildCards(); state.index = 0; render();
  } catch (error) { alert(`${name}: ${error.message}`); }
}

$('play').onclick = play; $('next').onclick = () => go(state.index + 1); $('prev').onclick = () => go(state.index - 1);
$('first').onclick = () => go(0); $('last').onclick = () => go(Number($('slider').max));
$('slider').oninput = e => go(Number(e.target.value));
$('speed').onchange = () => { if (state.timer) { stop(); play(); } };
$('trails').onchange = render;
$('clear').onclick = () => { state.missions = []; buildCards(); render(); };
$('file').onchange = e => { for (const f of e.target.files) f.text().then(text => addDocument(JSON.parse(text), f.name)); };
const drop = $('drop');
document.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
document.addEventListener('dragleave', () => drop.classList.remove('over'));
document.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); for (const f of e.dataTransfer.files) f.text().then(text => addDocument(JSON.parse(text), f.name)); });
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); play(); } else if (e.key === 'ArrowRight') go(state.index + 1); else if (e.key === 'ArrowLeft') go(state.index - 1);
  else if (e.key === 'Home') go(0); else if (e.key === 'End') go(Number($('slider').max));
});
$('title').textContent = TITLE;
document.title = TITLE + ' — Wildfire Player';
for (const m of EMBEDDED) { try { state.missions.push(extract(m.document, m.label, m.configuration)); } catch (error) { console.error(error); } }
buildCards();
// ?dia=N (ou ?tick=N) abre naquele dia; ?play=1 começa reproduzindo; ?trails=0 esconde os rastros.
const params = new URLSearchParams(location.search);
if (params.get('trails') === '0') $('trails').checked = false;
const start = params.get('dia') || params.get('tick');
if (start !== null) state.index = Math.max(0, Math.min(Number($('slider').max), Number(start) || 0));
render();
if (params.get('play') === '1' && state.missions.length) play();
</script>
</body>
</html>
'''


if __name__ == '__main__':
    sys.exit(main())
