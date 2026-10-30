"""Verificação reproduzível do checkout, sem chamadas LLM reais.

As integrações sobem serviços e agentes em contêineres; exigem Docker com Compose v2.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit-only', action='store_true', help='omite as integrações em contêineres Docker')
    args = parser.parse_args(argv)
    environment = dict(os.environ)
    environment.pop('ARIADNE_TEST_DOCKER', None)
    environment['GOCACHE'] = str(ROOT / '.ariadne/cache/go')
    environment['ARIADNE_PYTHON'] = sys.executable

    def run(command, *, cwd=ROOT, env=None):
        print('\n> ' + ' '.join(str(value) for value in command), flush=True)
        subprocess.run([str(value) for value in command], cwd=cwd, env=env or environment, check=True)

    run(['sh', 'tools/check-contract-freeze.sh'])
    run([sys.executable, 'tools/check-doc-links.py'])
    run(['go', 'test', './...'], cwd=ROOT / 'runtime')
    if not args.unit_only:
        from ariadne_sdk.compose import Compose
        print('\nDocker Compose ' + Compose.available(), flush=True)
        environment['ARIADNE_TEST_DOCKER'] = '1'
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'sdk/python/tests', '-q'])
    run([sys.executable, '-m', 'unittest', 'studies.scenarios.routing.test_agents', 'studies.scenarios.routing.test_mission', '-q'])
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
    print('\nVerificação concluída. Nenhuma chamada LLM real foi feita.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)
