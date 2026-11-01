"""Análise das evidências do cenário wildfire: linhas por missão, comparação e figuras.

    python -m studies.scenarios.wildfire.analysis <campanha ou execuções> [--output DIR] [--no-plots]
Com PNG e GIF: uv run --project sdk/python --with matplotlib python -m studies.scenarios.wildfire.analysis ...

Cada execução de ``./ariadne run`` ou observação de ``./ariadne campaign``
traz ``manifest.json`` (caso, configuração, drones e modo em ``metadata``) e
``mission-result.json``. A análise transforma cada uma em uma linha por
``mission.episode_metrics``, confere o provedor do planejador (substituto em
modo demo, OpenAI no modo real) e grava:

- ``results.json`` (linhas completas, com a curva por tique) e
  ``observations.csv`` (colunas planas);
- ``comparison.md``: médias por caso e configuração e a diferença pareada
  entre as duas configurações;
- ``curves-<caso>.svg``: cinzas por tique, uma linha fina por observação e
  a média em negrito por configuração;
- ``frames-<caso>-<configuração>.svg``: tira de quadros da grade (início,
  um quarto, metade, três quartos e fim) da primeira observação;
- ``summary.svg``: barras por caso com a área queimada de cada configuração;
- ``player-<caso>.html``: player interativo com as duas configurações lado a
  lado, tique a tique (``player.py``); ``player.html`` abre qualquer
  ``mission-result.json``.

Só biblioteca padrão. Com matplotlib disponível (``--no-plots`` desliga), as
mesmas figuras saem também em PNG e cada tira vira um GIF.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import uuid

from studies.scenarios.wildfire.agents.common import DEMO_PROVIDER
from studies.scenarios.wildfire.domain.cases import find_case
from studies.scenarios.wildfire.domain.world import coords, truth_at
from studies.scenarios.wildfire.mission import LABELS, episode_metrics, round_states
from studies.scenarios.wildfire.player import mission_entry, player_html

COLORS = {'ariadne': '#2a78d6', 'single-llm': '#eb6834', 'ink': '#0b0b0b', 'muted': '#52514e', 'grid': '#e4e3df',
          'surface': '#fcfcfb', 'vegetation': '#dfeedb', 'ash': '#4a4a4a', 'obstacle': '#1e1e1e', 'base': '#2a78d6',
          'base_dead': '#9aa5b1', 'structure': '#8e44ad', 'fire': {1: '#f6b26b', 2: '#e8742f', 3: '#c0392b'}}
CSV_COLUMNS = ['case', 'suite', 'configuration', 'drones', 'execution_kind', 'model', 'result', 'ticks', 'horizon',
               'burned', 'cells', 'burned_pct', 'fires_remaining', 'extinguished', 'drops', 'structures_burned',
               'structures_total', 'alert_structure_status', 'alert_reaction_ticks', 'drones_lost', 'drones_offline',
               'accepted_actions', 'rejected_actions', 'idle_actions', 'rounds', 'llm_calls', 'model_calls',
               'standing_orders_rounds', 'planner_latency_mean_s', 'planner_latency_max_s', 'input_tokens', 'output_tokens', 'bdi_cycles', 'max_parallel_steps',
               'reassignments', 'wall_seconds', 'mission_status', 'error', 'run']
MEAN_COLUMNS = ['burned_pct', 'burned', 'fires_remaining', 'structures_burned', 'drones_lost', 'rejected_actions',
                'idle_actions', 'extinguished', 'rounds', 'llm_calls', 'input_tokens', 'output_tokens', 'wall_seconds',
                'alert_reaction_ticks', 'planner_latency_mean_s', 'bdi_cycles']


# ---------------------------------------------------------------------------
# Leitura das evidências
# ---------------------------------------------------------------------------


def run_directories(paths):
    """Execuções (contêm ``manifest.json``) ou campanhas (``runs/*/manifest.json``)."""
    found = []
    for path in paths:
        path = Path(path).resolve()
        if (path / 'manifest.json').is_file():
            found.append(path)
        else:
            found.extend(sorted(candidate.parent for candidate in path.glob('runs/*/manifest.json')))
    return list(dict.fromkeys(found))


def check_provider(document, *, demo, model):
    """O planejador deve ser o substituto (demo) ou o modelo pedido (real)."""
    for item in document.get('rounds', []):
        metadata = (item.get('planner_result') or {}).get('metadata') or {}
        provider = metadata.get('provider')
        if provider in (None, 'none'):
            continue  # atalho sem modelo (sem fogo, horizonte, ordens permanentes)
        expected = DEMO_PROVIDER if demo else 'openai'
        if provider != expected or (not demo and model and metadata.get('model') != model):
            raise ValueError(f"round {item.get('round')}: planner provider/model {provider}/{metadata.get('model')} "
                             'differs from the requested configuration')


def row_for(directory, *, model):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    metadata = manifest.get('metadata') or {}
    case = find_case(metadata['case'], drones=metadata.get('drones'))
    configuration = metadata['configuration']
    demo = metadata.get('execution_kind') == 'deterministic-integration-demo'
    saved = directory / 'mission-result.json'
    document, error = {}, None
    if saved.is_file():
        document = json.loads(saved.read_text(encoding='utf-8'))
        try:
            check_provider(document, demo=demo, model=model)
        except ValueError as failure:
            error = str(failure)
    else:
        summary_path = directory / 'summary.json'
        summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.is_file() else {}
        error = summary.get('error') or f"run {summary.get('status', 'unknown')} without mission-result.json"
    row = episode_metrics(document, case=case, configuration=configuration, demo=demo)
    row.update(run=str(directory), execution_kind=metadata.get('execution_kind'), model=None if demo else model,
               burned_pct=(round(100 * row['burned'] / row['cells'], 2) if row.get('burned') is not None else None))
    if error:
        row.update(result='error', error=error)
    row['document'] = document
    return row


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return (round(statistics.fmean(values), 2), len(values)) if values else (None, 0)


def _fmt(value, n=None):
    if value is None:
        return 'ausente'
    text = f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{text} (n={n})' if n is not None else text


def group_rows(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row['case'], row['configuration']), []).append(row)
    return groups


def summary_table(rows):
    lines = ['| Caso | Drones | Configuração | n | Queimado (%) | Cinzas | Focos restantes | Estruturas perdidas | '
             'Drones perdidos | Rejeitadas | Ociosas | Contidas | Reação ao alerta (tiques) | Chamadas LLM | Latência média do modelo (s) | '
             'Tokens entrada/saída | Ciclos BDI | Tempo (s) |',
             '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|']
    for (case, configuration), items in sorted(group_rows(rows).items()):
        means = {key: _mean([row.get(key) for row in items]) for key in MEAN_COLUMNS}
        contained = sum(1 for row in items if row.get('result') == 'contained')
        drones = sorted({row['drones'] for row in items})
        lines.append(f"| {case} | {'/'.join(map(str, drones))} | {LABELS.get(configuration, configuration)} | {len(items)} | "
                     f"{_fmt(*means['burned_pct'])} | {_fmt(*means['burned'])} | {_fmt(*means['fires_remaining'])} | "
                     f"{_fmt(*means['structures_burned'])} | {_fmt(*means['drones_lost'])} | {_fmt(*means['rejected_actions'])} | "
                     f"{_fmt(*means['idle_actions'])} | {contained}/{len(items)} | {_fmt(*means['alert_reaction_ticks'])} | "
                     f"{_fmt(*means['llm_calls'])} | {_fmt(*means['planner_latency_mean_s'])} | "
                     f"{_fmt(*means['input_tokens'])}/{_fmt(*means['output_tokens'])} | {_fmt(*means['bdi_cycles'])} | "
                     f"{_fmt(*means['wall_seconds'])} |")
    return '\n'.join(lines) + '\n'


def paired_table(rows, baseline='single-llm', candidate='ariadne'):
    groups = group_rows(rows)
    cases = sorted({case for case, _ in groups})
    lines = [f'| Caso | Queimado {LABELS[candidate]} (%) | Queimado {LABELS[baseline]} (%) | Diferença (p.p.) | '
             'Contidas (cand. / base) | Estruturas perdidas (cand. / base) | Drones perdidos (cand. / base) | '
             'Rejeitadas (cand. / base) | Tokens (cand. / base) | Tempo s (cand. / base) |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for case in cases:
        a, b = groups.get((case, candidate), []), groups.get((case, baseline), [])
        if not a or not b:
            continue
        pa, pb = _mean([r.get('burned_pct') for r in a])[0], _mean([r.get('burned_pct') for r in b])[0]
        diff = None if pa is None or pb is None else round(pa - pb, 2)
        tokens = lambda items: _mean([(r['input_tokens'] or 0) + (r['output_tokens'] or 0) for r in items
                                      if r.get('input_tokens') is not None and r.get('output_tokens') is not None])[0]
        contained = lambda items: f"{sum(1 for r in items if r.get('result') == 'contained')}/{len(items)}"
        lines.append(f"| {case} | {_fmt(pa)} | {_fmt(pb)} | {_fmt(diff)} | {contained(a)} / {contained(b)} | "
                     f"{_fmt(_mean([r.get('structures_burned') for r in a])[0])} / {_fmt(_mean([r.get('structures_burned') for r in b])[0])} | "
                     f"{_fmt(_mean([r.get('drones_lost') for r in a])[0])} / {_fmt(_mean([r.get('drones_lost') for r in b])[0])} | "
                     f"{_fmt(_mean([r.get('rejected_actions') for r in a])[0])} / {_fmt(_mean([r.get('rejected_actions') for r in b])[0])} | "
                     f"{_fmt(tokens(a))} / {_fmt(tokens(b))} | "
                     f"{_fmt(_mean([r.get('wall_seconds') for r in a])[0])} / {_fmt(_mean([r.get('wall_seconds') for r in b])[0])} |")
    return '\n'.join(lines) + '\n'


def write_csv(rows, path):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ('' if row.get(key) is None else row.get(key)) for key in CSV_COLUMNS})


# ---------------------------------------------------------------------------
# Figuras em SVG (biblioteca padrão)
# ---------------------------------------------------------------------------


def _svg(width, height, body, title=None):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="12">')
    label = f'<title>{title}</title>' if title else ''
    return f'{head}{label}<rect width="{width}" height="{height}" fill="{COLORS["surface"]}"/>{body}</svg>\n'


def curves_svg(case_id, items):
    """Cinzas por tique: linhas finas por observação, média em negrito por configuração."""
    width, height, left, top, right, bottom = 720, 400, 60, 40, 20, 50
    series = {}
    for row in items:
        if row.get('curve'):
            series.setdefault(row['configuration'], []).append(row['curve'])
    if not series:
        return _svg(width, height, '', case_id)
    max_tick = max(point['tick'] for curves in series.values() for curve in curves for point in curve)
    max_burned = max(1, max(point['burned'] for curves in series.values() for curve in curves for point in curve))
    sx = (width - left - right) / max(max_tick, 1)
    sy = (height - top - bottom) / max_burned
    x = lambda tick: left + tick * sx
    y = lambda value: height - bottom - value * sy
    body = [f'<text x="{left}" y="22" font-size="15" fill="{COLORS["ink"]}">Área queimada por tique: {case_id}</text>']
    for value in range(0, max_burned + 1, max(1, max_burned // 5)):
        body.append(f'<line x1="{left}" y1="{y(value):.1f}" x2="{width - right}" y2="{y(value):.1f}" stroke="{COLORS["grid"]}"/>'
                    f'<text x="{left - 8}" y="{y(value) + 4:.1f}" text-anchor="end" fill="{COLORS["muted"]}">{value}</text>')
    for tick in range(0, max_tick + 1, max(1, max_tick // 10)):
        body.append(f'<text x="{x(tick):.1f}" y="{height - bottom + 16}" text-anchor="middle" fill="{COLORS["muted"]}">{tick}</text>')
    body.append(f'<text x="{(left + width - right) / 2:.1f}" y="{height - 8}" text-anchor="middle" fill="{COLORS["muted"]}">tique</text>')
    body.append(f'<text x="14" y="{(top + height - bottom) / 2:.1f}" transform="rotate(-90 14 {(top + height - bottom) / 2:.1f})" '
                f'text-anchor="middle" fill="{COLORS["muted"]}">células em cinzas</text>')
    legend_y = top
    for configuration, curves in sorted(series.items()):
        color = COLORS.get(configuration, COLORS['ink'])
        for curve in curves:
            points = ' '.join(f'{x(p["tick"]):.1f},{y(p["burned"]):.1f}' for p in curve)
            body.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1" opacity="0.35"/>')
        length = min(len(curve) for curve in curves)
        mean = [statistics.fmean(curve[i]['burned'] for curve in curves) for i in range(length)]
        points = ' '.join(f'{x(curves[0][i]["tick"]):.1f},{y(mean[i]):.1f}' for i in range(length))
        body.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        body.append(f'<rect x="{left + 10}" y="{legend_y}" width="18" height="4" fill="{color}"/>'
                    f'<text x="{left + 34}" y="{legend_y + 5}" fill="{COLORS["ink"]}">{LABELS.get(configuration, configuration)} '
                    f'(n={len(curves)}, final médio {mean[-1]:.1f})</text>')
        legend_y += 18
    return _svg(width, height, ''.join(body), f'Área queimada por tique: {case_id}')


def grid_svg_fragment(state, case, *, x0, y0, size, title):
    """Um quadro da grade como fragmento SVG em (x0, y0)."""
    truth = truth_at(case, state['tick'])
    width, height = int(state['width']), int(state['height'])
    ash, fires = set(state['ash']), state['fires']
    obstacles = set(state['obstacles'])
    bases = {b['at']: bid for bid, b in state['bases'].items()}
    dead = {state['bases'][bid]['at'] for bid in truth['disabled_bases'] if bid in state['bases']}
    structures = {**{c: s['name'] for c, s in state['structures'].items()}, **truth['hidden_structures']}
    body = [f'<text x="{x0}" y="{y0 - 6}" font-size="12" fill="{COLORS["ink"]}">{title}</text>']
    for yy in range(height):
        for xx in range(width):
            c = f'{xx},{yy}'
            fill = COLORS['vegetation']
            if c in obstacles:
                fill = COLORS['obstacle']
            elif c in ash:
                fill = COLORS['ash']
            elif c in fires:
                fill = COLORS['fire'][max(1, min(3, int(fires[c])))]
            body.append(f'<rect x="{x0 + xx * size}" y="{y0 + yy * size}" width="{size}" height="{size}" fill="{fill}" '
                        f'stroke="{COLORS["surface"]}" stroke-width="0.5"/>')
    for c, bid in bases.items():
        xx, yy = coords(c)
        color = COLORS['base_dead'] if c in dead else COLORS['base']
        body.append(f'<rect x="{x0 + xx * size + 1}" y="{y0 + yy * size + 1}" width="{size - 2}" height="{size - 2}" '
                    f'fill="{color}"/><text x="{x0 + xx * size + size / 2:.1f}" y="{y0 + yy * size + size * 0.75:.1f}" '
                    f'font-size="{size * 0.55:.1f}" text-anchor="middle" fill="white">{bid[-1]}</text>')
    for c, name in structures.items():
        xx, yy = coords(c)
        burned = c in ash
        body.append(f'<rect x="{x0 + xx * size + 2}" y="{y0 + yy * size + 2}" width="{size - 4}" height="{size - 4}" '
                    f'fill="{"none" if burned else COLORS["structure"]}" stroke="{COLORS["structure"]}" stroke-width="2">'
                    f'<title>{name}</title></rect>')
    for drone_id, drone in state['drones'].items():
        xx, yy = coords(drone['at'])
        cx, cy = x0 + xx * size + size / 2, y0 + yy * size + size / 2
        if drone.get('condition') == 'lost':
            body.append(f'<text x="{cx:.1f}" y="{cy + size * 0.3:.1f}" font-size="{size * 0.8:.1f}" text-anchor="middle" '
                        f'fill="{COLORS["ink"]}">×</text>')
            continue
        stroke = COLORS['muted'] if drone.get('condition') == 'offline' else COLORS['ink']
        body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size * 0.38:.1f}" fill="white" stroke="{stroke}" stroke-width="1.5"/>'
                    f'<text x="{cx:.1f}" y="{cy + size * 0.22:.1f}" font-size="{size * 0.5:.1f}" text-anchor="middle" '
                    f'fill="{stroke}">{drone_id[1:]}</text>')
    return ''.join(body)


def frames_svg(row, case, *, frames=5, size=12):
    """Tira de quadros: início, quartos e fim de uma missão."""
    states = round_states(row['document'], case)
    if len(states) < 2:
        return None
    picks = sorted({round(i * (len(states) - 1) / (frames - 1)) for i in range(frames)})
    width, height = int(case['width']), int(case['height'])
    gap, top = 16, 36
    total_w = gap + len(picks) * (width * size + gap)
    total_h = top + height * size + 64
    body = [f'<text x="{gap}" y="18" font-size="14" fill="{COLORS["ink"]}">{case["title"]} — '
            f'{LABELS.get(row["configuration"], row["configuration"])}: cinzas {row.get("burned")} de {row.get("cells")}, '
            f'drones perdidos {row.get("drones_lost")}, rejeitadas {row.get("rejected_actions")}</text>']
    for index, pick in enumerate(picks):
        state = states[pick]
        body.append(grid_svg_fragment(state, case, x0=gap + index * (width * size + gap), y0=top,
                                      size=size, title=f"tique {state['tick']}: {len(state['fires'])} focos, {len(state['ash'])} cinzas"))
    legend_y = top + height * size + 20
    legend = [('vegetação', COLORS['vegetation']), ('fogo 1', COLORS['fire'][1]), ('fogo 2', COLORS['fire'][2]),
              ('fogo 3', COLORS['fire'][3]), ('cinzas', COLORS['ash']), ('obstáculo', COLORS['obstacle']),
              ('base', COLORS['base']), ('base fora de serviço', COLORS['base_dead']), ('estrutura', COLORS['structure'])]
    xpos = gap
    for label, color in legend:
        body.append(f'<rect x="{xpos}" y="{legend_y}" width="12" height="12" fill="{color}"/>'
                    f'<text x="{xpos + 16}" y="{legend_y + 10}" fill="{COLORS["ink"]}">{label}</text>')
        xpos += 16 + 7 * len(label) + 18
    body.append(f'<text x="{gap}" y="{legend_y + 30}" fill="{COLORS["muted"]}">círculos: drones (número = id); × drone perdido; '
                'estrutura vazada = queimada; estruturas anunciadas só pelo rádio aparecem desde o anúncio.</text>')
    return _svg(total_w, total_h, ''.join(body), case['title'])


def summary_svg(rows):
    """Barras por caso: área queimada (%) de cada configuração, média das observações."""
    groups = group_rows(rows)
    cases = sorted({case for case, _ in groups})
    configurations = sorted({configuration for _, configuration in groups})
    if not cases:
        return _svg(10, 10, '')
    width, left, top, bottom, right = 720, 60, 40, 70, 20
    slot = (width - left - right) / len(cases)
    bar = slot / (len(configurations) + 1)
    height = 360
    sy = (height - top - bottom) / 100
    y = lambda value: height - bottom - value * sy
    body = [f'<text x="{left}" y="22" font-size="15" fill="{COLORS["ink"]}">Área queimada ao final (% das células), média por caso</text>']
    for value in range(0, 101, 20):
        body.append(f'<line x1="{left}" y1="{y(value):.1f}" x2="{width - right}" y2="{y(value):.1f}" stroke="{COLORS["grid"]}"/>'
                    f'<text x="{left - 8}" y="{y(value) + 4:.1f}" text-anchor="end" fill="{COLORS["muted"]}">{value}</text>')
    for i, case in enumerate(cases):
        for j, configuration in enumerate(configurations):
            items = groups.get((case, configuration), [])
            value, n = _mean([r.get('burned_pct') for r in items])
            if value is None:
                continue
            x0 = left + i * slot + (j + 0.5) * bar
            color = COLORS.get(configuration, COLORS['ink'])
            body.append(f'<rect x="{x0:.1f}" y="{y(value):.1f}" width="{bar:.1f}" height="{(height - bottom) - y(value):.1f}" fill="{color}"/>'
                        f'<text x="{x0 + bar / 2:.1f}" y="{y(value) - 4:.1f}" text-anchor="middle" fill="{COLORS["ink"]}">{value:.0f}</text>')
        body.append(f'<text x="{left + (i + 0.5) * slot:.1f}" y="{height - bottom + 18}" text-anchor="middle" fill="{COLORS["ink"]}">{case}</text>')
    legend_x = left
    for configuration in configurations:
        body.append(f'<rect x="{legend_x}" y="{height - 22}" width="14" height="14" fill="{COLORS.get(configuration, COLORS["ink"])}"/>'
                    f'<text x="{legend_x + 18}" y="{height - 11}" fill="{COLORS["ink"]}">{LABELS.get(configuration, configuration)}</text>')
        legend_x += 18 + 7 * len(LABELS.get(configuration, configuration)) + 24
    return _svg(width, height, ''.join(body), 'Área queimada ao final')


# ---------------------------------------------------------------------------
# PNG e GIF (matplotlib opcional)
# ---------------------------------------------------------------------------


def _matplotlib():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        return plt
    except Exception:
        return None


def curves_png(case_id, items, path):
    plt = _matplotlib()
    if plt is None:
        return False
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for configuration in sorted({r['configuration'] for r in items}):
        curves = [r['curve'] for r in items if r['configuration'] == configuration and r.get('curve')]
        if not curves:
            continue
        color = COLORS.get(configuration, COLORS['ink'])
        for curve in curves:
            ax.plot([p['tick'] for p in curve], [p['burned'] for p in curve], color=color, alpha=0.3, linewidth=1)
        length = min(len(c) for c in curves)
        ax.plot([curves[0][i]['tick'] for i in range(length)],
                [statistics.fmean(c[i]['burned'] for c in curves) for i in range(length)],
                color=color, linewidth=3, label=f'{LABELS.get(configuration, configuration)} (n={len(curves)})')
    ax.set_xlabel('tique')
    ax.set_ylabel('células em cinzas')
    ax.set_title(f'Área queimada por tique: {case_id}')
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return True


def _draw_state(ax, state, case):
    import matplotlib.patches as patches
    truth = truth_at(case, state['tick'])
    width, height = int(state['width']), int(state['height'])
    ash, fires, obstacles = set(state['ash']), state['fires'], set(state['obstacles'])
    dead = {state['bases'][bid]['at'] for bid in truth['disabled_bases'] if bid in state['bases']}
    structures = {**{c: s['name'] for c, s in state['structures'].items()}, **truth['hidden_structures']}
    ax.clear()
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for yy in range(height):
        for xx in range(width):
            c = f'{xx},{yy}'
            fill = COLORS['vegetation']
            if c in obstacles:
                fill = COLORS['obstacle']
            elif c in ash:
                fill = COLORS['ash']
            elif c in fires:
                fill = COLORS['fire'][max(1, min(3, int(fires[c])))]
            ax.add_patch(patches.Rectangle((xx, yy), 1, 1, facecolor=fill, edgecolor=COLORS['surface'], linewidth=0.3))
    for bid, base in state['bases'].items():
        xx, yy = coords(base['at'])
        ax.add_patch(patches.Rectangle((xx + 0.1, yy + 0.1), 0.8, 0.8,
                                       facecolor=COLORS['base_dead'] if base['at'] in dead else COLORS['base']))
        ax.text(xx + 0.5, yy + 0.5, bid[-1], ha='center', va='center', color='white', fontsize=7)
    for c in structures:
        xx, yy = coords(c)
        ax.add_patch(patches.Rectangle((xx + 0.15, yy + 0.15), 0.7, 0.7, facecolor='none' if c in ash else COLORS['structure'],
                                       edgecolor=COLORS['structure'], linewidth=1.5))
    for drone_id, drone in state['drones'].items():
        xx, yy = coords(drone['at'])
        if drone.get('condition') == 'lost':
            ax.text(xx + 0.5, yy + 0.5, '×', ha='center', va='center', color=COLORS['ink'], fontsize=10)
            continue
        edge = COLORS['muted'] if drone.get('condition') == 'offline' else COLORS['ink']
        ax.add_patch(patches.Circle((xx + 0.5, yy + 0.5), 0.36, facecolor='white', edgecolor=edge, linewidth=1))
        ax.text(xx + 0.5, yy + 0.5, drone_id[1:], ha='center', va='center', color=edge, fontsize=6)
    ax.set_title(f"tique {state['tick']}: {len(fires)} focos, {len(ash)} cinzas", fontsize=9)


def frames_gif(row, case, path):
    plt = _matplotlib()
    if plt is None:
        return False
    try:
        from matplotlib.animation import FuncAnimation, PillowWriter
    except Exception:
        return False
    states = round_states(row['document'], case)
    fig, ax = plt.subplots(figsize=(5, 5.3))
    fig.suptitle(f"{case['title']} — {LABELS.get(row['configuration'], row['configuration'])}", fontsize=9)
    animation = FuncAnimation(fig, lambda i: _draw_state(ax, states[i], case), frames=len(states), interval=600)
    try:
        animation.save(path, writer=PillowWriter(fps=2))
    except Exception:
        plt.close(fig)
        return False
    plt.close(fig)
    return True


def summary_png(rows, path):
    plt = _matplotlib()
    if plt is None:
        return False
    groups = group_rows(rows)
    cases = sorted({case for case, _ in groups})
    configurations = sorted({configuration for _, configuration in groups})
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.8 / max(len(configurations), 1)
    for j, configuration in enumerate(configurations):
        values = [_mean([r.get('burned_pct') for r in groups.get((case, configuration), [])])[0] or 0 for case in cases]
        ax.bar([i + j * width for i in range(len(cases))], values, width=width,
               color=COLORS.get(configuration, COLORS['ink']), label=LABELS.get(configuration, configuration))
    ax.set_xticks([i + width * (len(configurations) - 1) / 2 for i in range(len(cases))])
    ax.set_xticklabels(cases)
    ax.set_ylabel('área queimada ao final (%)')
    ax.set_title('Área queimada ao final, média por caso')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


def write_report(rows, output, *, model, plots):
    output.mkdir(parents=True, exist_ok=True)
    public = [{k: v for k, v in row.items() if k != 'document'} for row in rows]
    (output / 'results.json').write_text(json.dumps(public, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_csv(public, output / 'observations.csv')
    kinds = sorted({row['execution_kind'] for row in rows if row.get('execution_kind')})
    figures = []
    for case_id in sorted({row['case'] for row in rows}):
        items = [row for row in rows if row['case'] == case_id and row.get('curve')]
        if not items:
            continue
        (output / f'curves-{case_id}.svg').write_text(curves_svg(case_id, items), encoding='utf-8')
        figures.append(f'curves-{case_id}.svg')
        if plots and curves_png(case_id, items, output / f'curves-{case_id}.png'):
            figures.append(f'curves-{case_id}.png')
        for configuration in sorted({row['configuration'] for row in items}):
            first = next(row for row in items if row['configuration'] == configuration)
            case = find_case(case_id, drones=first['drones'])
            strip = frames_svg(first, case)
            if strip:
                name = f'frames-{case_id}-{configuration}'
                (output / f'{name}.svg').write_text(strip, encoding='utf-8')
                figures.append(f'{name}.svg')
                if plots and frames_gif(first, case, output / f'{name}.gif'):
                    figures.append(f'{name}.gif')
        players = [mission_entry(row['document'], label=LABELS.get(row['configuration'], row['configuration']),
                                 configuration=row['configuration'])
                   for configuration in sorted({row['configuration'] for row in items})
                   for row in [next(row for row in items if row['configuration'] == configuration)] if row.get('document')]
        if players:
            case = find_case(case_id, drones=items[0]['drones'])
            (output / f'player-{case_id}.html').write_text(player_html(players, title=f"Incêndio: {case['title']}"), encoding='utf-8')
            figures.append(f'player-{case_id}.html')
    (output / 'summary.svg').write_text(summary_svg(rows), encoding='utf-8')
    figures.append('summary.svg')
    (output / 'player.html').write_text(player_html([], title='Wildfire Player'), encoding='utf-8')
    figures.append('player.html')
    if plots and summary_png(rows, output / 'summary.png'):
        figures.append('summary.png')
    report = [f"# Wildfire: comparação por caso\n\nExecução: {', '.join(kinds) or 'desconhecida'}. Modelo: {model}. "
              f"Laço de missão no orquestrador Go. Gerado em {datetime.now(timezone.utc).isoformat()}.\n",
              f'{len(rows)} observações; {len({row["case"] for row in rows})} casos distintos.\n',
              'Queimado = células em cinzas ao final sobre o total de células. Cada célula mostra a média das observações '
              'daquele caso/configuração e seu n válido. "Contidas" conta missões que terminaram sem fogo. "Reação ao '
              'alerta" é o número de tiques entre o anúncio da estrutura no rádio e o primeiro drone a até duas células '
              'dela; ausente quando o caso não tem alerta ou nenhum drone chegou. Tokens só são somados quando entrada e '
              'saída estão presentes em todas as rodadas reais. Não há intervalos de confiança nem testes de '
              'significância; n=1 é uma observação descritiva. Observações com erro permanecem listadas.\n',
              '## Resumo por caso e configuração\n', summary_table(rows),
              '## Diferença pareada (Ariadne menos Piloto LLM)\n', paired_table(rows),
              '## Figuras\n', ''.join(f'- [{name}]({name})\n' for name in figures),
              '\n## Erros registrados\n',
              ''.join(f"- {row['case']} / {row['configuration']}: {row['error']}\n" for row in rows if row.get('error')) or 'Nenhum.\n']
    (output / 'comparison.md').write_text('\n'.join(report), encoding='utf-8')
    return figures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inputs', nargs='+', type=Path, help='pastas de campanha ou de execução')
    parser.add_argument('--output', type=Path, help='pasta dos relatórios; padrão: analysis-<id> dentro da primeira entrada')
    parser.add_argument('--model', help='modelo esperado dos planejadores reais (padrão: LLM_MODEL ou gpt-5.6-luna)')
    parser.add_argument('--no-plots', action='store_true', help='só SVG, CSV e Markdown, sem matplotlib')
    args = parser.parse_args(argv)
    model = args.model or os.getenv('LLM_MODEL', 'gpt-5.6-luna')
    directories = run_directories(args.inputs)
    if not directories:
        parser.error('no run with manifest.json found in the given paths')
    output = (args.output or args.inputs[0].resolve() / ('analysis-' + uuid.uuid4().hex[:8])).resolve()
    rows = [row_for(directory, model=model) for directory in directories]
    write_report(rows, output, model=model, plots=not args.no_plots)
    print(summary_table(rows))
    print(f'Resultados: {output / "results.json"}\nTabela: {output / "comparison.md"}')
    return 1 if any(row.get('error') for row in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
