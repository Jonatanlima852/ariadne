"""Coletor da v3: uma missão por caso/configuração, cada uma em contêineres próprios.

Da raiz:
  uv run --project sdk/python python -m studies.scenarios.logistics.v3.benchmarks.run \
    --suite stress --configurations ariadne-v3 single-llm-v3 --repeat 3

Cada observação chama o mesmo executor de ``./ariadne run`` sobre
``v3/scenario.py`` com ``LOGISTICS_V3_CASE``/``LOGISTICS_V3_CONFIGURATION``,
portanto sobe registry, orquestrador, planejador, entregadores e executor em
contêineres, aplica a missão e os derruba. O ``MissionResult`` de cada missão
é copiado para ``missions/<caso>-<configuração>-r<n>.json`` (legível no
visualizador de missão) e vira uma linha de ``results.json`` por
``mission.episode_metrics``; as evidências completas ficam em ``runs/``.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from ariadne_sdk.campaign import environment
from ariadne_sdk.execution import run_experiment
from studies.scenarios.logistics.v2.domain.world import RULES, validate_case
from studies.scenarios.logistics.v3.domain.cases import load_cases
from studies.scenarios.logistics.v3.mission import (
    CONFIGURATIONS, DELIVERY_AGENTS, DEMO_PROVIDER, MAX_ROUNDS, RETRY_POLICY, SELECTION_POLICY, episode_metrics, limits,
)

HERE = Path(__file__).resolve().parents[1]
V2 = HERE.parent / 'v2'
SCENARIO = HERE / 'scenario.py'


def table(rows):
    lines = ['| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | Rodadas | LLM | Tokens entrada/saída | Ciclos BDI | Paralelo máx. | Reatrib. | Resultado |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        seconds = 'ausente' if r['wall_seconds'] is None else f"{r['wall_seconds']:.3f}"
        lines.append(f"| {r['case']} | {r['configuration']} | {r['delivered']}/{r['total_orders']} | {r['on_time']} | "
                     f"{r['rejected_actions']} | {seconds} | {r['distance']} | {r['energy_consumed']} | {r['rounds']} | "
                     f"{r['llm_calls']} | {r['input_tokens']}/{r['output_tokens']} | {r['bdi_cycles']} | "
                     f"{r['max_parallel_steps']} | {r['reassignments']} | {r['result']} |")
    return '\n'.join(lines) + '\n'


def source_hashes():
    files = [p for root in (HERE, V2 / 'domain', V2 / 'datasets', V2 / 'agents' / 'energy_manager', V2 / 'agents' / 'single_llm',
                            V2 / 'demonstrations', V2 / 'execution')
             for p in root.rglob('*') if p.is_file() and (p.suffix in ('.py', '.yaml', '.json') or p.name == 'Dockerfile')
             and '__pycache__' not in p.parts]
    return {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def check_provider(document, *, demo, model):
    """Como na v2: o planejador remoto deve ser o substituto (demo) ou o modelo pedido."""
    for item in document.get('rounds', []):
        metadata = (item.get('planner_result') or {}).get('metadata') or {}
        provider = metadata.get('provider')
        if provider in (None, 'none'):
            continue  # atalho sem modelo (tudo entregue, nada viável)
        expected = DEMO_PROVIDER if demo else 'openai'
        if provider != expected or (not demo and model and metadata.get('model') != model):
            raise ValueError(f"round {item.get('round')}: planner provider/model {provider}/{metadata.get('model')} "
                             f'differs from the requested configuration')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--suite', choices=['basic', 'stress', 'all'], default='basic')
    parser.add_argument('--cases', nargs='+', help='Fixed IDs from the chosen suite')
    parser.add_argument('--repeat', type=int, default=1, help='Observations per case/configuration')
    parser.add_argument('--configurations', nargs='+', choices=sorted(CONFIGURATIONS), default=['ariadne-v3', 'single-llm-v3'])
    parser.add_argument('--demo', action='store_true', help='Deterministic substitutes; not a real LLM benchmark')
    parser.add_argument('--model', help='Model expected from the LLM planners')
    parser.add_argument('--rpc-timeout', type=float, default=3600, help='Seconds the client waits for one mission')
    parser.add_argument('--output', type=Path, default=Path('.ariadne/logistics-v3'))
    args = parser.parse_args(argv)
    args.model = args.model or os.getenv('LLM_MODEL', 'gpt-5.6-luna')
    if args.repeat < 1 or len(set(args.configurations)) != len(args.configurations):
        parser.error('Use a positive --repeat and distinct configurations')
    try:
        cases = load_cases(args.suite, args.cases)
    except ValueError as error:
        parser.error(str(error))
    for case in cases:
        validate_case(case)
    directory = args.output.resolve() / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (directory / 'missions').mkdir(parents=True)
    kind = 'deterministic-integration-demo' if args.demo else 'real-llm'
    rows = []
    manifest = {'schema_version': 4, 'study': 'logistics-v3', 'suite': args.suite,
                'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING',
                'repeat': args.repeat, 'planned_observations': len(cases) * len(args.configurations) * args.repeat,
                'execution_kind': kind, 'model': None if args.demo else args.model,
                'max_rounds': MAX_ROUNDS, 'limits': limits().to_dict(),
                'retry_policy': RETRY_POLICY, 'selection_policy': SELECTION_POLICY, 'delivery_agents': DELIVERY_AGENTS,
                'cases': cases, 'configurations': args.configurations,
                'planner_capabilities': {c: CONFIGURATIONS[c] for c in args.configurations},
                'rules': RULES.strip(), 'loop': 'Go mission loop (contract 2.0.0); incidents fired by the execute agent',
                'backend': 'docker-compose', 'scenario': str(SCENARIO), 'source_sha256': source_hashes()}
    print(f'Execução: {kind}; evidências: {directory}', flush=True)

    def save():
        manifest['finished_observations'] = len(rows)
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        (directory / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        (directory / 'comparison.md').write_text(f'Execução: {kind}. Modelo: {manifest["model"]}. '
                                                 f'Laço de missão no orquestrador Go; {DELIVERY_AGENTS} entregadores BDI.\n\n' + table(rows))
    save()
    try:
        for repetition in range(1, args.repeat + 1):
            configurations = args.configurations if repetition % 2 else list(reversed(args.configurations))
            for case in cases:
                for configuration in configurations:
                    name = f"{case['id']}-{configuration}-r{repetition}"
                    error, document, run = None, {}, None
                    try:
                        with environment({'LOGISTICS_V3_CASE': case['id'], 'LOGISTICS_V3_CONFIGURATION': configuration,
                                          'LOGISTICS_V3_DEMO': '1' if args.demo else '0'}):
                            run, summary = run_experiment(SCENARIO, output_root=directory / 'runs',
                                                          task_timeout=args.rpc_timeout)
                        saved = run / 'mission-result.json'
                        if not saved.is_file():
                            raise RuntimeError(summary.get('error') or f"run {summary['status']} without mission-result.json")
                        document = json.loads(saved.read_text())
                        check_provider(document, demo=args.demo, model=args.model)
                    except Exception as failure:  # a missão que não voltou ainda vira uma observação
                        error = f'{type(failure).__name__}: {failure}'
                    mission_file = directory / 'missions' / f'{name}.json'
                    mission_file.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
                    row = episode_metrics(document, case=case, configuration=configuration, demo=args.demo)
                    row.update(model=manifest['model'], backend='docker-compose', repetition=repetition,
                               run=str(run.relative_to(directory)) if run else None,
                               mission_file=str(mission_file.relative_to(directory)))
                    if row.get('wall_seconds') is None and run is not None:
                        row['wall_seconds'] = round(summary.get('elapsed_ms', 0) / 1000, 4)
                    if error:
                        row.update(result='error', error=error, stop_reason=error)
                    rows.append(row)
                    save()
                    print(table([row]), flush=True)
        manifest['status'] = 'FAILED' if any(r['error'] for r in rows) else 'COMPLETED'
    except KeyboardInterrupt:
        manifest['status'] = 'CANCELLED'
        raise
    finally:
        manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(f'Resultados: {directory / "results.json"}\nTabela: {directory / "comparison.md"}')
    return 1 if any(r['error'] for r in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
