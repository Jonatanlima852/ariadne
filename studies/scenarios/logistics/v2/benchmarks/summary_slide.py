"""Create a measured 16:9 summary for slides from a fully paired real collection.

uv run --no-project --with matplotlib python -m studies.scenarios.logistics.v2.benchmarks.summary_slide \
  --input studies/scenarios/logistics/v2/results/stress-lean/results.json \
  --output studies/scenarios/logistics/v2/results/stress-lean/analysis
"""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from studies.scenarios.logistics.v2.benchmarks.analyze import normalize, LABELS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    content = args.input.read_bytes()
    raw = json.loads(content)
    rows, (kind, model) = normalize(raw)
    configs = list(dict.fromkeys(r['configuration'] for r in rows))
    if kind != 'real-llm' or len(configs) != 2 or 'single-llm' not in configs:
        parser.error('Use one real collection with Single LLM and one hybrid configuration')
    configs = ['single-llm', next(c for c in configs if c != 'single-llm')]
    groups = {c: [r for r in rows if r['configuration'] == c] for c in configs}
    identities = [{(r['case'], r['repetition'] or 1) for r in groups[c]} for c in configs]
    if identities[0] != identities[1] or any(len(ids) != len(groups[c]) for c, ids in zip(configs, identities)):
        parser.error('Paired case/repetition identities are required; no orphan or duplicate observations')
    for case, rep in identities[0]:
        pair = [next(r for r in groups[c] if r['case'] == case and (r['repetition'] or 1) == rep) for c in configs]
        if pair[0]['total_orders'] != pair[1]['total_orders']:
            parser.error('Orders differ within a pair')
    totals = {}
    for c in configs:
        group = groups[c]
        fields = ('delivered', 'total_orders', 'on_time', 'wall_seconds', 'total_tokens', 'rejected_actions')
        total = {f: sum(r[f] for r in group) if all(r[f] is not None for r in group) else None for f in fields}
        total.update(observations=len(group), errors=sum(r['error'] is not None for r in group),
                     mean_wall_seconds=mean(r['wall_seconds'] for r in group),
                     mean_tokens=mean(r['total_tokens'] for r in group) if all(r['total_tokens'] is not None for r in group) else None)
        totals[c] = total
    token_pairs = []
    for case, rep in sorted(identities[0]):
        pair = [next(r for r in groups[c] if r['case'] == case and (r['repetition'] or 1) == rep) for c in configs]
        if all(r['total_tokens'] is not None for r in pair):
            token_pairs.append(pair)
    paired_token_totals = {c: sum(pair[i]['total_tokens'] for pair in token_pairs) if token_pairs else None
                           for i, c in enumerate(configs)}
    for c in configs:
        totals[c]['mean_paired_tokens'] = paired_token_totals[c] / len(token_pairs) if token_pairs else None
    baseline, hybrid = (totals[c] for c in configs)
    speedup = baseline['mean_wall_seconds'] / hybrid['mean_wall_seconds'] if hybrid['mean_wall_seconds'] else None
    token_reduction = (100 * (1 - paired_token_totals[configs[1]] / paired_token_totals[configs[0]])
                       if paired_token_totals[configs[0]] else None)
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {'execution_kind': kind, 'model': model, 'source_sha256': hashlib.sha256(content).hexdigest(),
               'paired_observations': len(identities[0]), 'cases': len({case for case, _ in identities[0]}),
               'totals': totals, 'speedup_mean_wall_seconds': speedup,
               'paired_token_observations': len(token_pairs), 'paired_token_totals': paired_token_totals,
               'token_reduction_on_known_pairs_pct': token_reduction}
    (args.output / 'headline.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig = plt.figure(figsize=(16, 9), facecolor='#f3f6f2')
    fig.text(.05, .93, 'LOGÍSTICA · COMPARAÇÃO MEDIDA', fontsize=15, weight='bold', color='#466b59')
    fig.text(.05, .865, f'{LABELS.get(configs[1], configs[1])} e Single LLM', fontsize=29, weight='bold', color='#183b2a')
    fig.text(.05, .815, f"{summary['cases']} casos · {baseline['observations']} episódios por configuração · mesmo modelo: {model}", fontsize=16, color='#53685e')
    def fmt(v, digits=1):
        return 'não disponível' if v is None else f'{v:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    cards = [('Tempo real médio / episódio', 'mean_wall_seconds', ' s'),
             ('Tokens médios / episódio com uso medido', 'mean_paired_tokens', ''),
             ('Pedidos entregues', 'delivered', ''), ('Pedidos entregues no prazo', 'on_time', '')]
    for i, (title, field, unit) in enumerate(cards):
        x, y = .05 + (i % 2) * .47, .46 - (i // 2) * .28
        fig.patches.append(FancyBboxPatch((x, y), .43, .23, boxstyle='round,pad=0.012', transform=fig.transFigure,
                                         facecolor='white', edgecolor='#d9e3dc', zorder=0))
        fig.text(x+.018, y+.174, title, fontsize=17, weight='bold', color='#254b37')
        for j, c in enumerate(configs):
            total = totals[c]
            value = (f"{fmt(total[field], 0)} / {fmt(total['total_orders'], 0)}" if field in ('delivered', 'on_time')
                     else fmt(total[field], 1 if field == 'mean_wall_seconds' else 0) + unit)
            fig.text(x+.018, y+.111-j*.063, LABELS.get(c, c), fontsize=16, color='#526b5c')
            fig.text(x+.405, y+.111-j*.063, value, fontsize=24, weight='bold', ha='right',
                     color='#2f65ad' if j == 0 else '#19735b')
    fig.text(.05, .105, f"Razão dos tempos médios: {fmt(speedup)}× · redução de tokens: {fmt(token_reduction)}%", fontsize=21, weight='bold', color='#214e38')
    fig.text(.05, .062, f"Ações rejeitadas: {baseline['rejected_actions']} / {hybrid['rejected_actions']} · erros: {baseline['errors']} / {hybrid['errors']} (Single / híbrido). Tokens: {len(token_pairs)}/{len(identities[0])} pares com uso conhecido em ambos.", fontsize=12, color='#53685e')
    fig.text(.05, .028, 'Tempo e atendimento incluem todos os pares, inclusive parciais e erros. Tokens ausentes excluem o par somente da comparação de tokens. Casos fixos; sem alegação de otimalidade.', fontsize=10, color='#6e8175')
    for suffix in ('png', 'svg'):
        fig.savefig(args.output / f'headline.{suffix}', dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
