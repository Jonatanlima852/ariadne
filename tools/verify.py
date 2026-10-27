"""Verificação reproduzível do checkout, sem Docker ou chamadas LLM reais."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit-only', action='store_true', help='omite build e integração com processos Go')
    parser.add_argument('--no-inspector', action='store_true', help='omite verificações do visualizador')
    args = parser.parse_args(argv)
    if not args.no_inspector:
        from ariadne_sdk.doctor import node_supported, tool_version, NODE_REQUIREMENT
        installed = tool_version('node', '--version')
        if not node_supported(installed):
            raise SystemExit(f'Inspector exige Node {NODE_REQUIREMENT}; encontrado {installed}')
    environment = dict(os.environ)
    environment.pop('ARIADNE_TEST_RUNTIME_DIR', None)
    environment['GOCACHE'] = str(ROOT / '.ariadne/cache/go')
    environment['ARIADNE_PYTHON'] = sys.executable

    def run(command, *, cwd=ROOT, env=None):
        print('\n> ' + ' '.join(str(value) for value in command), flush=True)
        subprocess.run([str(value) for value in command], cwd=cwd, env=env or environment, check=True)

    run(['sh', 'tools/check-contract-freeze.sh'])
    run([sys.executable, 'tools/check-doc-links.py'])
    run(['go', 'test', './...'], cwd=ROOT / 'runtime')
    if not args.unit_only:
        binaries = ROOT / '.ariadne/bin'
        binaries.mkdir(parents=True, exist_ok=True)
        for service in ('registry', 'orchestrator', 'messaging'):
            run(['go', 'build', '-o', binaries / f'ariadne-{service}', f'./services/{service}/cmd'], cwd=ROOT / 'runtime')
        environment['ARIADNE_TEST_RUNTIME_DIR'] = str(binaries)
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'sdk/python/tests', '-q'])
    run([sys.executable, '-m', 'unittest', 'studies.scenarios.logistics.tests.test_domain', 'studies.scenarios.logistics.tests.test_study', 'studies.scenarios.logistics.v2.tests.test_integration', 'studies.scenarios.routing.test_agents', 'studies.scenarios.routing.test_mission', 'studies.test_layout', '-q'])
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/launcher', '-q'])
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/runtime_metrics', '-q'])

    # Verifica a instalação mínima real, separada do ambiente de testes LLM.
    core = ROOT / '.ariadne/verify/core'
    core_env = {**environment, 'UV_PROJECT_ENVIRONMENT': str(core)}
    run(['uv', 'sync', '--locked', '--project', 'sdk/python', '--no-default-groups'], env=core_env)
    run([core / 'bin/python', '-c', '''
import importlib.util
from ariadne_sdk.execution import load_scenario
assert importlib.util.find_spec("openai") is None
assert importlib.util.find_spec("pydantic") is None
for path in ("studies/scenarios/basic_task/scenario.py", "sdk/python/tests/fixtures/route_choice.py", "studies/scenarios/meeting/scenario.py"):
    load_scenario(path).definition()
print("Core SDK works without OpenAI/Pydantic")
'''])
    if not args.no_inspector:
        run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/inspector', '-p', 'test_serve.py', '-q'])
        run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=ROOT / 'tools/inspector')
        run(['node', '--test', 'model.test.js', 'presentation.test.js'], cwd=ROOT / 'tools/inspector')
        run(['npm', 'run', 'build'], cwd=ROOT / 'tools/inspector')
        run(['uv', 'run', '--locked', '--project', 'tools/inspector/api', 'python', '-m', 'pytest',
             'tools/inspector/api/test_app.py', '-q'])
    print('\nVerificação concluída. Nenhuma chamada LLM real foi feita.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)
