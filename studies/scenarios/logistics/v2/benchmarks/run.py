"""Comparison client for independently deployed Ariadne agents (Docker Compose)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from ariadne_sdk import RuntimeClient
import grpc
from google.protobuf.json_format import MessageToDict
from contract.v1 import contract_pb2 as pb, contract_pb2_grpc as rpc
from studies.scenarios.logistics.v2.execution.episode import Episode
from studies.scenarios.logistics.v2.execution.lean import LeanEpisode
from studies.scenarios.logistics.v2.domain.world import validate_case

HERE = Path(__file__).resolve().parents[1]


def table(rows):
    lines = ['| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | LLM | Tokens entrada/saída | Resultado |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['configuration']} | {r['delivered']}/{r['total_orders']} | {r['on_time']} | {r['rejected_actions']} | {r['wall_seconds']:.3f} | {r['distance']} | {r['energy_consumed']} | {r['llm_calls']} | {r['input_tokens']}/{r['output_tokens']} | {r['result']} |")
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['basic', 'stress', 'all'], default='basic')
    parser.add_argument('--cases', nargs='+', help='Fixed IDs from the chosen suite')
    parser.add_argument('--repeat', type=int, default=1, help='Observations per case/configuration')
    parser.add_argument('--configurations', nargs='+', choices=['single-llm', 'ariadne', 'ariadne-lean'], default=['single-llm', 'ariadne'])
    parser.add_argument('--demo', action='store_true', help='Deterministic substitutes; not a real LLM benchmark')
    parser.add_argument('--model', help='Same model for all LLM calls in both configurations')
    parser.add_argument('--max-rounds', type=int, default=20)
    parser.add_argument('--orchestrator-addr', default=os.getenv('ORCHESTRATOR_ADDR', 'localhost:55052'))
    parser.add_argument('--registry-addr', default=os.getenv('REGISTRY_ADDR', 'localhost:55051'))
    parser.add_argument('--output', type=Path, default=Path('.ariadne/logistics-v2'))
    args = parser.parse_args(argv)
    args.model = args.model or os.getenv('LLM_MODEL', 'gpt-5.6-luna')
    if args.max_rounds < 1 or args.repeat < 1 or len(set(args.configurations)) != len(args.configurations):
        parser.error('Use positive --max-rounds/--repeat and distinct configurations')
    files = ['basic.json'] if args.suite == 'basic' else ['stress.json'] if args.suite == 'stress' else ['basic.json', 'stress.json']
    cases = [case for name in files for case in json.loads((HERE / 'datasets' / name).read_text())]
    for case in cases:
        validate_case(case)
    if args.cases:
        unknown = set(args.cases) - {c['id'] for c in cases}
        if unknown:
            parser.error(f'Unknown cases: {sorted(unknown)}')
        cases = [c for c in cases if c['id'] in args.cases]
    team = ['OrderInterpreter', 'MissionDecomposer', 'IncidentAnalyst', 'OperationsReporter',
            'InventoryManager', 'ResourceAllocator', 'RoutePlanner', 'EnergyManager',
            'ConstraintSupervisor', 'MissionExecutor']
    lean_team = ['OrderInterpreter', 'MissionCoordinator', 'InventoryManager', 'ResourceAllocator',
                 'RoutePlanner', 'EnergyManager', 'ConstraintSupervisor', 'MissionExecutor']
    roles_by_configuration = {'single-llm': ['SingleLLM'], 'ariadne': team, 'ariadne-lean': lean_team}
    required = list(dict.fromkeys(role for config in args.configurations for role in roles_by_configuration[config]))
    registered = {}
    with grpc.insecure_channel(args.registry_addr) as channel:
        registry = rpc.RegistryServiceStub(channel)
        for role in required:
            agents = registry.DiscoverAgents(pb.DiscoverAgentsRequest(
                required_capabilities=['logistics-v2-' + role], status_filter=pb.AGENT_STATUS_ALIVE), timeout=10).agents
            if len(agents) != 1:
                parser.error(f'Expected one healthy {role}; found {len(agents)}. Start docker/compose.yaml with --wait.')
            descriptor = agents[0]
            if role in ('SingleLLM', 'OrderInterpreter', 'MissionDecomposer', 'IncidentAnalyst', 'OperationsReporter'):
                expected = 'logistics-v2-demo' if args.demo else 'logistics-v2-llm'
                if descriptor.runtime != expected:
                    parser.error(f'{role} runtime is {descriptor.runtime}; expected {expected}. Match --demo to LOGISTICS_V2_DEMO in Compose.')
            registered[role] = MessageToDict(descriptor, preserving_proto_field_name=True)
    directory = args.output.resolve() / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True)
    rows = []
    kind = 'deterministic-integration-demo' if args.demo else 'real-llm'
    manifest = {'schema_version':2, 'study':'logistics-v2', 'suite':args.suite,
                'created_at':datetime.now(timezone.utc).isoformat(), 'status':'RUNNING',
                'repeat':args.repeat, 'planned_observations':len(cases)*len(args.configurations)*args.repeat,
                'execution_kind':kind, 'model':None if args.demo else args.model,
                'max_rounds':args.max_rounds, 'cases':cases, 'configurations':args.configurations,
                'policies':{'ariadne': 'original-ten-agents', 'ariadne-lean': 'lean-v1'},
                'rules': 'sequential time; whole orders; incidents before next action at accepted-action threshold',
                'backend':'docker-compose', 'orchestrator_addr':args.orchestrator_addr,
                'registry_addr':args.registry_addr, 'registered_agents':registered,
                'source_sha256':{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in HERE.rglob('*') if p.is_file() and (p.suffix in ('.py', '.yaml') or p.name == 'Dockerfile')}}
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(f'Execução: {kind}; evidências: {directory}', flush=True)
    def save():
        manifest['finished_observations'] = len(rows)
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        (directory/'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
        (directory/'comparison.md').write_text(f'Execução: {kind}. Modelo: {manifest["model"]}.\n\n'+table(rows))
    try:
        for repetition in range(1, args.repeat + 1):
            configurations = args.configurations if repetition % 2 else list(reversed(args.configurations))
            for case in cases:
                for strategy in configurations:
                    with RuntimeClient(f"logistics-v2-{case['id']}-{strategy}-r{repetition}", args.orchestrator_addr) as client:
                        episode = LeanEpisode if strategy == 'ariadne-lean' else Episode
                        result = episode(client, case, strategy, demo=args.demo, max_rounds=args.max_rounds,
                                         model=args.model).run()
                    result.update(model=manifest['model'], backend='docker-compose', repetition=repetition,
                                  suite=case.get('suite', 'basic'), trace_id=client.trace_id)
                    result['registered_agents'] = [registered[role] for role in roles_by_configuration[strategy]]
                    rows.append(result)
                    save()
                    print(table([result]), flush=True)
        manifest['status'] = 'FAILED' if any(r['error'] for r in rows) else 'COMPLETED'
    except KeyboardInterrupt:
        manifest['status'] = 'CANCELLED'
        raise
    except Exception as error:
        manifest.update(status='FAILED', error=str(error))
        raise
    finally:
        manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(f'Resultados: {directory / "results.json"}\nTabela: {directory / "comparison.md"}')
    return 1 if any(r['error'] for r in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
