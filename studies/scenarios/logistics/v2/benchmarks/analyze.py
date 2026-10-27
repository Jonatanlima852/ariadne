"""Exporta métricas já coletadas; não usa SDK, runtime, Docker nem chamadas LLM.

Da raiz do repositório (matplotlib fica no ambiente temporário do uv):
  uv run --no-project --with matplotlib python -m studies.scenarios.logistics.v2.benchmarks.analyze \
    --input studies/scenarios/logistics/v2/results/real/results.json \
    --output /tmp/logistics-analysis --title 'Logística: comparação básica'

Somente CSV e Markdown, usando apenas a biblioteca padrão:
  python -m studies.scenarios.logistics.v2.benchmarks.analyze --input results.json \
    --output /tmp/logistics-analysis --no-plots

Cada execução deve conter um único execution_kind e model. As médias são por
caso/configuração, nunca uma distribuição que trate casos como repetições.
As figuras comparam single-llm a cada outra configuração, em diretórios separados,
usando apenas os casos com observações de ambos. Os órfãos continuam nas tabelas.
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean
import sys


BASELINE = 'single-llm'
LABELS = {'single-llm': 'Single LLM', 'ariadne': 'Ariadne',
          'ariadne-lean': 'Ariadne enxuta'}
METRICS = {
    'delivery_pct': ('Pedidos atendidos', '% dos pedidos', 'higher'),
    'on_time_pct': ('Pedidos entregues no prazo', '% dos pedidos', 'higher'),
    'wall_seconds': ('Tempo real total', 'segundos', 'lower'),
    'total_tokens': ('Tokens de entrada + saída', 'tokens', 'lower'),
    'distance': ('Distância percorrida', 'unidades de distância', 'lower'),
    'energy_consumed': ('Energia consumida', 'unidades de energia', 'lower'),
    'rejected_actions': ('Ações rejeitadas', 'ações', 'lower'),
    'input_tokens': ('Tokens de entrada', 'tokens', 'lower'),
    'output_tokens': ('Tokens de saída', 'tokens', 'lower'),
}
RAW_FIELDS = ['observation', 'case', 'configuration', 'execution_kind', 'model',
              'suite', 'repetition', 'total_orders', 'delivered', 'on_time',
              *METRICS, 'result', 'error', 'stop_reason']


def number(row, key, index):
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Observação {index}: {key} deve ser um número finito ou null.')
    if value < 0:
        raise ValueError(f'Observação {index}: {key} não pode ser negativo.')
    return value


def normalize(document):
    if not isinstance(document, list) or not document:
        raise ValueError('A entrada deve ser um array JSON não vazio de observações.')
    rows = []
    partitions = set()
    for index, row in enumerate(document, 1):
        if not isinstance(row, dict):
            raise ValueError(f'Observação {index}: esperado um objeto JSON.')
        for key in ('case', 'configuration', 'execution_kind'):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f'Observação {index}: {key} deve ser uma string não vazia.')
        if row.get('model') is not None and not isinstance(row['model'], str):
            raise ValueError(f'Observação {index}: model deve ser string ou null.')
        partitions.add((row['execution_kind'], row.get('model')))
        entry = {key: row.get(key) for key in RAW_FIELDS}
        entry['observation'] = index
        for key in ('total_orders', 'delivered', 'on_time', 'wall_seconds',
                    'input_tokens', 'output_tokens', 'distance', 'energy_consumed',
                    'rejected_actions'):
            entry[key] = number(row, key, index)
        total, delivered, on_time = (entry[key] for key in ('total_orders', 'delivered', 'on_time'))
        if total is not None and delivered is not None and delivered > total:
            raise ValueError(f'Observação {index}: delivered excede total_orders.')
        if on_time is not None and delivered is not None and on_time > delivered:
            raise ValueError(f'Observação {index}: on_time excede delivered.')
        entry['delivery_pct'] = 100 * delivered / total if total and delivered is not None else None
        entry['on_time_pct'] = 100 * on_time / total if total and on_time is not None else None
        incoming, outgoing = entry['input_tokens'], entry['output_tokens']
        entry['total_tokens'] = incoming + outgoing if incoming is not None and outgoing is not None else None
        rows.append(entry)
    if len(partitions) != 1:
        choices = ', '.join(f'{kind} / {model or "não informado"}'
                            for kind, model in sorted(partitions, key=str))
        raise ValueError('Modos/modelos distintos não podem ser agregados. '
                         f'Separe os arquivos por execution_kind e model: {choices}.')
    return rows, next(iter(partitions))


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['case'], row['configuration'])].append(row)
    summaries = []
    for (case, configuration), observations in groups.items():
        entry = {'case': case, 'configuration': configuration, 'n_observations': len(observations),
                 'error_runs': sum(row['error'] is not None for row in observations),
                 'result_counts': dict(Counter(str(row['result']) for row in observations))}
        for metric in METRICS:
            values = [row[metric] for row in observations if row[metric] is not None]
            entry[metric + '_mean'] = mean(values) if values else None
            entry[metric + '_n'] = len(values)
        summaries.append(entry)
    configurations = list(dict.fromkeys(row['configuration'] for row in rows))
    comparisons = {}
    for configuration in configurations:
        if configuration == BASELINE:
            continue
        baseline_cases = {case for case, config in groups if config == BASELINE}
        hybrid_cases = {case for case, config in groups if config == configuration}
        comparisons[configuration] = {
            'paired_cases': [case for case in dict.fromkeys(row['case'] for row in rows)
                             if case in baseline_cases & hybrid_cases],
            'baseline_only': sorted(baseline_cases - hybrid_cases),
            'hybrid_only': sorted(hybrid_cases - baseline_cases),
        }
    return summaries, comparisons


def csv_value(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in fields} for row in rows)


def display(value):
    return 'ausente' if value is None else f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def escape(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def estimate(entry, metric):
    return f'{display(entry[metric + "_mean"])} (n={entry[metric + "_n"]})'


def safe_directory(configuration):
    # Hash evita colisões entre nomes diferentes que produzam o mesmo slug.
    slug = re.sub(r'[^a-zA-Z0-9_-]+', '-', configuration).strip('-')[:64] or 'configuration'
    digest = hashlib.sha256(configuration.encode()).hexdigest()[:8]
    return f'single-llm-vs-{slug}-{digest}'


def plot_comparison(plt, output, title, partition, summaries, configuration, cases):
    lookup = {(row['case'], row['configuration']): row for row in summaries}
    output.mkdir(parents=True, exist_ok=True)
    figures = []
    pairs = [('01-atendimento', ('delivery_pct', 'on_time_pct')),
             ('02-tempo-e-tokens', ('wall_seconds', 'total_tokens')),
             ('03-distancia-e-energia', ('distance', 'energy_consumed'))]
    configurations = [BASELINE, configuration]
    colors = ['#28698c', '#c76422']
    for filename, metrics in pairs:
        figure, axes = plt.subplots(1, 2, figsize=(16, max(4.5, .72 * len(cases) + 2.5)),
                                   squeeze=False)
        kind, model = partition
        mode_label = ('Demonstração determinística de integração — sem LLM real'
                      if 'demo' in kind else f'{kind} · modelo: {model or "não informado"}')
        figure.suptitle(f'{title}\n{LABELS.get(configuration, configuration)} × Single LLM\n{mode_label}',
                        fontsize=13, fontweight='bold', linespacing=1.4)
        for axis, metric in zip(axes[0], metrics):
            heading, unit, direction = METRICS[metric]
            entries = [lookup[(case, config)] for case in cases for config in configurations]
            known = [entry[metric + '_mean'] for entry in entries if entry[metric + '_mean'] is not None]
            maximum = max(known, default=0)
            axis.set_xlim(0, 125 if metric.endswith('_pct') else max(1, maximum * 1.37))
            for config_index, config in enumerate(configurations):
                for case_index, case in enumerate(cases):
                    entry = lookup[(case, config)]
                    value, count = entry[metric + '_mean'], entry[metric + '_n']
                    position = case_index + (-.2 if config_index == 0 else .2)
                    if value is None:
                        axis.text(0, position, 'ausente (n=0)', va='center', fontsize=9,
                                  color=colors[config_index])
                    else:
                        axis.barh(position, value, height=.34, color=colors[config_index],
                                  label=LABELS.get(config, config) if case_index == 0 else None)
                        axis.annotate(f'{display(value)} · n={count}', (value, position),
                                      xytext=(4, 0), textcoords='offset points', va='center', fontsize=9)
            axis.set_yticks(range(len(cases)), labels=cases, fontsize=9)
            axis.invert_yaxis()
            axis.set_title(heading + (' ↑' if direction == 'higher' else ' ↓'), fontsize=12, pad=14)
            axis.set_xlabel(unit)
            axis.grid(axis='x', color='#e2e8ef')
            axis.set_axisbelow(True)
            axis.spines[['top', 'right', 'left']].set_visible(False)
        # Legenda independente da presença ou ausência de valores no primeiro caso.
        from matplotlib.patches import Patch
        figure.legend(handles=[Patch(color=color, label=LABELS.get(config, config))
                               for color, config in zip(colors, configurations)],
                      loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(.5, .045))
        figure.text(.5, .015, 'Média por caso/configuração; n = observações com a métrica. '
                    'Ausente ≠ zero. Interprete custos junto ao atendimento.',
                    ha='center', fontsize=9, color='#455568')
        figure.tight_layout(rect=(0, .10, 1, .91))
        for extension in ('svg', 'png'):
            path = output / f'{filename}.{extension}'
            figure.savefig(path, dpi=180, facecolor='white')
            figures.append(path)
        plt.close(figure)
    return figures


def report(title, source, partition, rows, summaries, comparisons, figures, plots_requested):
    kind, model = partition
    lines = [f'# {title}', '', f'Fonte: `{source}`. Modo: `{kind}`. Modelo: `{model or "não informado"}`.',
             '', f'{len(rows)} observações; {len({row["case"] for row in rows})} casos distintos.', '',
             'Atendimento = entregues / total de pedidos × 100. No prazo = entregues no prazo / '
             'total de pedidos × 100, incluindo os não atendidos no denominador. '
             'Cada célula mostra a média das observações daquele caso/configuração e seu n válido. '
             'Valores ausentes permanecem vazios no CSV e aparecem como “ausente” aqui; zero é um valor medido. '
             'Quando total_orders é zero ou ausente, as porcentagens ficam ausentes.', '',
             'Tokens totais só são calculados quando entrada e saída estão presentes na mesma observação. '
             'Tempo real inclui todas as fases medidas pelo coletor, inclusive relatório quando aplicável. '
             'Distância e energia baixas devem ser interpretadas junto ao atendimento: uma execução parcial '
             'pode consumir menos simplesmente porque deixou pedidos sem entrega.', '',
             'Não há intervalos de confiança ou testes de significância. Casos diferentes não são tratados '
             'como repetições; n=1 é uma observação descritiva. Repetições com falha e resultados parciais '
             'permanecem nas tabelas e nas médias quando há métricas medidas. As médias de métricas '
             'diferentes podem ter amostras válidas diferentes, indicadas por n. O pareamento das figuras '
             'é por caso e configuração dentro do mesmo modo/modelo; as repetições de cada configuração '
             'podem ter contagens diferentes. O JSON de entrada precisa representar as mesmas regras e '
             'casos para que a comparação seja válida.', '']
    if 'demo' in kind:
        lines.extend(['**Demonstração determinística de integração: não mede desempenho de LLM.**', ''])
    lines.extend(['## Cobertura das comparações', ''])
    if not comparisons:
        lines.extend(['Não há configuração híbrida para comparar com Single LLM; nenhuma figura comparativa foi produzida.', ''])
    for configuration, coverage in comparisons.items():
        lines.extend([f'**{escape(LABELS.get(configuration, configuration))} × Single LLM**: '
                      f'{len(coverage["paired_cases"])} casos pareados.', '',
                      'Casos presentes somente no baseline, excluídos desta comparação: '
                      + (', '.join(map(escape, coverage['baseline_only'])) or 'nenhum') + '.', '',
                      'Casos presentes somente nesta configuração, excluídos desta comparação: '
                      + (', '.join(map(escape, coverage['hybrid_only'])) or 'nenhum') + '.', ''])
    lines.extend(['## Todas as observações resumidas por caso', '',
                  '| Caso | Configuração | n total | Atendidos (%) | No prazo (%) | Tempo real (s) | Tokens | Distância | Energia | Rejeitadas | Execuções com erro | Resultados |',
                  '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|'])
    for row in summaries:
        cells = [escape(row['case']), escape(LABELS.get(row['configuration'], row['configuration'])),
                 str(row['n_observations']), *(estimate(row, key) for key in
                 ('delivery_pct', 'on_time_pct', 'wall_seconds', 'total_tokens', 'distance',
                  'energy_consumed', 'rejected_actions')), str(row['error_runs']),
                 escape(json.dumps(row['result_counts'], ensure_ascii=False))]
        lines.append('| ' + ' | '.join(cells) + ' |')
    errors = [row for row in rows if row['error'] is not None]
    if errors:
        lines.extend(['', '## Erros registrados', ''])
        lines.extend(f'- Observação {row["observation"]}, {escape(row["case"])} / '
                     f'{escape(row["configuration"])}: {escape(row["error"])}' for row in errors)
    lines.extend(['', '## Arquivos', '', '- [Observações e métricas derivadas](observations.csv).',
                  '- [Médias e contagens válidas por caso/configuração](case_summary.csv).'])
    lines.extend(f'- [{path.parent.name}/{path.name}]({path.as_posix()}).'
                 for path in figures)
    if not figures:
        lines.extend(['', 'Nenhuma figura exportada. ' + ('Não há casos pareados.' if plots_requested
                      else 'A opção --no-plots solicita somente tabelas.')])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, type=Path, help='Array results.json já coletado')
    parser.add_argument('--output', required=True, type=Path, help='Diretório de tabelas e figuras')
    parser.add_argument('--title', default='Logística v2: comparação por caso')
    parser.add_argument('--no-plots', action='store_true', help='Usar apenas biblioteca padrão: CSV e Markdown')
    args = parser.parse_args(argv)
    try:
        source = args.input.resolve()
        content = source.read_bytes()
        rows, partition = normalize(json.loads(content))
        summaries, comparisons = summarize(rows)
        plt = None
        if not args.no_plots:
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
            except ImportError as error:
                raise ValueError('Matplotlib não está instalado. Para figuras sem alterar dependências do '
                                 'projeto, execute: uv run --no-project --with matplotlib python -m '
                                 'studies.scenarios.logistics.v2.benchmarks.analyze --input CAMINHO --output DIRETORIO. '
                                 'Para somente CSV/Markdown, acrescente --no-plots.') from error
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        previous_manifest = output / 'analysis_manifest.json'
        if previous_manifest.exists():
            previous = json.loads(previous_manifest.read_text(encoding='utf-8'))
            if (previous.get('execution_kind'), previous.get('model')) != partition:
                raise ValueError('O diretório de saída já contém outro modo/modelo. '
                                 'Escolha outro --output para preservar análises separadas.')
        reserved = [output / name for name in ('observations.csv', 'case_summary.csv', 'analysis.md', 'analysis_manifest.json')]
        if source in reserved:
            raise ValueError('A entrada não pode coincidir com um arquivo de saída.')
        write_csv(output / 'observations.csv', rows, RAW_FIELDS)
        fields = ['case', 'configuration', 'n_observations', 'error_runs', 'result_counts',
                  *(field for metric in METRICS for field in (metric + '_mean', metric + '_n'))]
        write_csv(output / 'case_summary.csv', summaries, fields)
        figures = []
        if plt is not None:
            for configuration, coverage in comparisons.items():
                if coverage['paired_cases']:
                    figures.extend(plot_comparison(plt, output / safe_directory(configuration), args.title,
                                                   partition, summaries, configuration, coverage['paired_cases']))
        relative_figures = [path.relative_to(output) for path in figures]
        (output / 'analysis.md').write_text(report(args.title, source, partition, rows, summaries,
                                                  comparisons, relative_figures, not args.no_plots), encoding='utf-8')
        manifest = {'source': str(source), 'source_sha256': hashlib.sha256(content).hexdigest(),
                    'created_at': datetime.now(timezone.utc).isoformat(), 'title': args.title,
                    'execution_kind': partition[0], 'model': partition[1], 'observations': len(rows),
                    'comparisons': comparisons, 'figures': [path.as_posix() for path in relative_figures],
                    'aggregation': 'arithmetic mean within case/configuration; per-metric valid n'}
        (output / 'analysis_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f'Análise: {output / "analysis.md"}\nCSV: {output / "case_summary.csv"}\nFiguras: {len(figures)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
