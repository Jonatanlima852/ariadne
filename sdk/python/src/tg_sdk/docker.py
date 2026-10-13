"""Adaptador da CLI única para o backend Docker do checkout."""
import os
from pathlib import Path
import subprocess

SCENARIOS = ('demo', 'workflow-sequential', 'failure-reassignment', 'messaging-basic',
             'heterogeneous-route', 'logistics-mission')


def command(operation, *arguments, replace=True):
    root = Path(os.getenv('TG_ROOT', Path(__file__).resolve().parents[4]))
    script = root / 'tools/launcher/docker.sh'
    if not script.is_file():
        raise ValueError('Docker scenarios require a checkout; configure TG_ROOT to its path')
    args = ['sh', str(script), operation, *(str(value) for value in arguments)]
    environment = {**os.environ, 'TG_ROOT': str(root)}
    if replace:
        os.execvpe('sh', args, environment)
    return subprocess.run(args, env=environment).returncode
