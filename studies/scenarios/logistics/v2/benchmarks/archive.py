"""Replay and preserve Docker collections without merging experimental conditions.

Example: python -m studies.scenarios.logistics.v2.benchmarks.archive --name stress-lean <run-directory>
Use --allow-incomplete to preserve a cancelled collection with its missing pairs.
"""
import argparse
import hashlib
import json
from pathlib import Path
from studies.scenarios.logistics.v2.execution.episode import metrics
from studies.scenarios.logistics.v2.benchmarks.run import table
from studies.scenarios.logistics.v2.domain.world import initial, incidents, apply

HERE = Path(__file__).resolve().parents[1]


def archive(sources, name, allow_incomplete=False):
    if not name or Path(name).name != name or name in ('.', '..'):
        raise ValueError('Archive name must be one directory name')
    rows, collections, cases = [], [], {}
    conditions = set()
    protocol = None
    for source in sources:
        manifest = json.loads((source / 'manifest.json').read_text())
        source_protocol = {key: manifest.get(key) for key in ('max_rounds', 'rules', 'policies', 'source_sha256')}
        if protocol is None:
            protocol = source_protocol
        elif source_protocol != protocol:
            raise ValueError('Collections differ in limits, rules, policies or recorded source hashes; preserve them separately')
        conditions.add((manifest['suite'], manifest['execution_kind'], manifest['model'], manifest.get('repeat', 1)))
        collections.append({'directory': str(source),
                            'raw_results_sha256': hashlib.sha256((source / 'results.json').read_bytes()).hexdigest(),
                            'manifest': manifest})
        for case in manifest['cases']:
            if case['id'] in cases and cases[case['id']] != case:
                raise ValueError('Different worlds share a case ID')
            cases[case['id']] = case
        rows.extend(json.loads((source / 'results.json').read_text()))
    if len(conditions) != 1:
        raise ValueError('Preserve suites, execution kinds, models and repetition counts separately')
    suite, kind, model, repeat = next(iter(conditions))
    configs = list(dict.fromkeys(config for collection in collections for config in collection['manifest']['configurations']))
    expected = {(case, config, rep) for case in cases for config in configs for rep in range(1, repeat + 1)}
    seen = set()
    for row in rows:
        key = (row['case'], row['configuration'], row.get('repetition', 1))
        if key not in expected or key in seen:
            raise ValueError('Unexpected or duplicate observation')
        seen.add(key)
        state = initial(cases[row['case']])
        for item in row['state']['history']:
            if 'incident' in item:
                incidents(state, cases[row['case']]['incidents'])
            else:
                error = apply(state, item['action'])
                if (error is None) != item['accepted']:
                    raise ValueError('Acceptance replay mismatch')
        if state != row['state'] or any(row[k] != value for k, value in metrics(state).items()):
            raise ValueError('Final state or metrics do not match replay')
        # Omit only repeated copies; raw evidence is retained at source paths.
        for call in row['calls']:
            if call['role'] == 'MissionExecutor':
                call.pop('output', None)
        for workflow in row['workflows']:
            workflow.pop('steps', None)
            workflow.pop('output', None)
    missing = sorted(expected - seen)
    if missing and not allow_incomplete:
        raise ValueError(f'{len(missing)} observations missing; use --allow-incomplete to label a partial archive')
    target = HERE / 'results' / name
    if target.exists():
        raise ValueError(f'Archive exists; preserve it instead of overwriting: {target}')
    target.mkdir(parents=True)
    manifest = {'schema_version': 2, 'study': 'logistics-v2', 'suite': suite, 'backend': 'docker-compose',
                'execution_kind': kind, 'model': model, 'repeat': repeat,
                'created_at': collections[0]['manifest']['created_at'],
                'status': 'CANCELLED' if missing else 'FAILED' if any(r['error'] for r in rows) else 'COMPLETED',
                'planned_observations': len(expected), 'finished_observations': len(rows),
                'cases': list(cases.values()), 'configurations': configs,
                'missing_observations': [{'case': case, 'configuration': config, 'repetition': rep}
                                         for case, config, rep in missing],
                'collections': collections}
    summary = []
    for config in configs:
        group = [row for row in rows if row['configuration'] == config]
        fields = ('delivered', 'total_orders', 'on_time', 'rejected_actions', 'wall_seconds',
                  'wall_seconds_before_report', 'reporting_seconds', 'distance', 'energy_consumed',
                  'llm_calls', 'input_tokens', 'output_tokens')
        summary.append({'configuration': config, 'observations': len(group),
                        **{key: sum(row[key] for row in group) if group and all(row.get(key) is not None for row in group) else None
                           for key in fields}, 'operational_errors': sum(bool(row['error']) for row in group)})
    for filename, document in [('results.json', rows), ('manifest.json', manifest), ('summary.json', summary)]:
        (target / filename).write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
    note = f'{suite} · {kind} · Docker · {repeat} observação(ões) por caso/configuração.\n\n'
    if missing:
        note += f'**Coleta incompleta:** {len(rows)}/{len(expected)} observações. Não compare totais de grupos com cobertura diferente.\n\n'
    (target / 'comparison.md').write_text(note + table(rows))
    evidence = {'backend': 'docker-compose', 'replayed_observations': len(rows),
                'collections': [{k: v for k, v in collection.items() if k != 'manifest'} for collection in collections],
                'preservation': 'Only repeated workflow and executor-state copies omitted. Final states, histories, metrics and specialist decisions retained.'}
    (target / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(f'{target}: {len(rows)} observations replayed; {len(missing)} missing.')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--allow-incomplete', action='store_true')
    parser.add_argument('sources', nargs='+', type=Path)
    args = parser.parse_args()
    archive(args.sources, args.name, args.allow_incomplete)


if __name__ == '__main__':
    main()
