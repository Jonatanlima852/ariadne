"""Coletor da v3: uma missão por caso/configuração contra um orquestrador em execução.

Da raiz, com o Compose da v3 no ar (ver docker/README.md):
  uv run --project sdk/python python -m studies.scenarios.logistics.v3.benchmarks.run \
    --suite stress --configurations ariadne-v3 single-llm-v3 --repeat 3

Não há controlador de episódio: o cliente envia ``RunMission`` e o laço roda
no orquestrador Go. Cada ``MissionResult`` é salvo inteiro em
``missions/<caso>-<configuração>-r<n>.json`` (legível no visualizador de
missão) e vira uma linha de ``results.json`` por ``mission.episode_metrics``.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import grpc
from google.protobuf.json_format import MessageToDict

from ariadne_sdk import RuntimeClient
from contract.v1 import contract_pb2 as pb, contract_pb2_grpc as rpc
from studies.scenarios.logistics.v2.domain.world import RULES, validate_case
from studies.scenarios.logistics.v3.agents.common import llm_runtime
from studies.scenarios.logistics.v3.domain.adapters import DELIVERY_CAPABILITY, EXECUTE_CAPABILITY
from studies.scenarios.logistics.v3.domain.cases import load_cases
from studies.scenarios.logistics.v3.mission import (
    CONFIGURATIONS, DELIVERY_AGENTS, DEMO_PROVIDER, MAX_ROUNDS, RETRY_POLICY, SELECTION_POLICY, episode_metrics, limits,
    mission_for,
)

HERE = Path(__file__).resolve().parents[1]
V2 = HERE.parent / 'v2'


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


def discover(parser, args):
    """Confere no Registry os agentes de cada configuração pedida; devolve suas descrições."""
    required = {}
    for configuration in args.configurations:
        required[CONFIGURATIONS[configuration]] = (1, True)
        required[EXECUTE_CAPABILITY] = (1, False)
        if configuration == 'ariadne-v3':
            required[DELIVERY_CAPABILITY] = (args.delivery_agents, False)
    registered = {}
    with grpc.insecure_channel(args.registry_addr) as channel:
        registry = rpc.RegistryServiceStub(channel)
        for capability, (count, llm) in required.items():
            agents = registry.DiscoverAgents(pb.DiscoverAgentsRequest(
                required_capabilities=[capability], status_filter=pb.AGENT_STATUS_ALIVE), timeout=10).agents
            if len(agents) != count:
                parser.error(f'Expected {count} healthy agent(s) with {capability}; found {len(agents)}. '
                             'Start docker/compose.yaml with --wait.')
            for descriptor in agents:
                if llm and descriptor.runtime != llm_runtime(args.demo):
                    parser.error(f'{descriptor.agent_id} runtime is {descriptor.runtime}; expected {llm_runtime(args.demo)}. '
                                 'Match --demo to LOGISTICS_V3_DEMO in Compose.')
                registered[descriptor.agent_id] = MessageToDict(descriptor, preserving_proto_field_name=True)
    return registered


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
    parser.add_argument('--model', help='Model expected from the remote LLM planners')
    parser.add_argument('--max-rounds', type=int, default=MAX_ROUNDS)
    parser.add_argument('--delivery-agents', type=int, default=DELIVERY_AGENTS, help='Expected BDI delivery agents (= max_parallel)')
    parser.add_argument('--rpc-timeout', type=float, default=3600, help='Seconds the client waits for one mission')
    parser.add_argument('--orchestrator-addr', default=os.getenv('ORCHESTRATOR_ADDR', 'localhost:55062'))
    parser.add_argument('--registry-addr', default=os.getenv('REGISTRY_ADDR', 'localhost:55061'))
    parser.add_argument('--output', type=Path, default=Path('.ariadne/logistics-v3'))
    args = parser.parse_args(argv)
    args.model = args.model or os.getenv('LLM_MODEL', 'gpt-5.6-luna')
    if args.max_rounds < 1 or args.repeat < 1 or args.delivery_agents < 1 or len(set(args.configurations)) != len(args.configurations):
        parser.error('Use positive --max-rounds/--repeat/--delivery-agents and distinct configurations')
    try:
        cases = load_cases(args.suite, args.cases)
    except ValueError as error:
        parser.error(str(error))
    for case in cases:
        validate_case(case)
    registered = discover(parser, args)
    directory = args.output.resolve() / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (directory / 'missions').mkdir(parents=True)
    kind = 'deterministic-integration-demo' if args.demo else 'real-llm'
    rows = []
    manifest = {'schema_version': 3, 'study': 'logistics-v3', 'suite': args.suite,
                'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING',
                'repeat': args.repeat, 'planned_observations': len(cases) * len(args.configurations) * args.repeat,
                'execution_kind': kind, 'model': None if args.demo else args.model,
                'max_rounds': args.max_rounds, 'limits': limits(args.max_rounds, args.delivery_agents).to_dict(),
                'retry_policy': RETRY_POLICY, 'selection_policy': SELECTION_POLICY, 'delivery_agents': args.delivery_agents,
                'cases': cases, 'configurations': args.configurations,
                'planner_capabilities': {c: CONFIGURATIONS[c] for c in args.configurations},
                'rules': RULES.strip(), 'loop': 'Go mission loop (contract 2.0.0); incidents fired by the execute agent',
                'backend': 'docker-compose', 'orchestrator_addr': args.orchestrator_addr,
                'registry_addr': args.registry_addr, 'registered_agents': registered,
                'source_sha256': source_hashes()}
    print(f'Execução: {kind}; evidências: {directory}', flush=True)

    def save():
        manifest['finished_observations'] = len(rows)
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        (directory / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        (directory / 'comparison.md').write_text(f'Execução: {kind}. Modelo: {manifest["model"]}. '
                                                 f'Laço de missão no orquestrador Go; {args.delivery_agents} entregadores BDI.\n\n' + table(rows))
    save()
    try:
        for repetition in range(1, args.repeat + 1):
            configurations = args.configurations if repetition % 2 else list(reversed(args.configurations))
            for case in cases:
                for configuration in configurations:
                    mission = mission_for(case, configuration, max_rounds=args.max_rounds, delivery_agents=args.delivery_agents)
                    name = f"{case['id']}-{configuration}-r{repetition}"
                    started = time.perf_counter()
                    error, document = None, {}
                    try:
                        with RuntimeClient(f'logistics-v3-{name}', args.orchestrator_addr) as client:
                            result = client.run_mission(mission.goal, context=mission.context, limits=mission.limits,
                                                        planner_capability=mission.planner_capability,
                                                        retry_policy=mission.retry_policy, selection_policy=mission.selection_policy,
                                                        metadata=mission.metadata,
                                                        rpc_timeout=args.rpc_timeout)
                            document = result.to_dict()
                            check_provider(document, demo=args.demo, model=args.model)
                    except Exception as failure:  # a missão que não voltou ainda vira uma observação
                        error = f'{type(failure).__name__}: {failure}'
                    wall = round(time.perf_counter() - started, 4)
                    mission_file = directory / 'missions' / f'{name}.json'
                    mission_file.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
                    row = episode_metrics(document, case=case, configuration=configuration, demo=args.demo)
                    row.update(wall_seconds=wall, model=manifest['model'], backend='docker-compose', repetition=repetition,
                               trace_id=getattr(client, 'trace_id', None), mission_file=str(mission_file.relative_to(directory)))
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
