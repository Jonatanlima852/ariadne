"""Inicia e encerra API e Vite juntos, sem executar agentes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.request import urlopen
import uuid

from ariadne_sdk.doctor import node_supported, tool_version, NODE_REQUIREMENT
from ariadne_sdk.execution import Processes

ROOT = Path(__file__).resolve().parents[2]
INSPECTOR = ROOT / 'tools/inspector'


def port(value):
    value = int(value)
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError('porta deve estar entre 1 e 65535')
    return value


def available(port_number):
    with socket.socket() as channel:
        channel.bind(('127.0.0.1', port_number))


def ready(url, identity, *, api=False):
    try:
        with urlopen(url, timeout=.5) as response:
            body = response.read(1024 * 1024).decode()
        return json.loads(body).get('session') == identity if api else f'content="{identity}"' in body
    except (OSError, ValueError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=port, default=4173)
    parser.add_argument('--api-port', type=port, default=8787)
    parser.add_argument('--ready-timeout', type=int, default=90)
    parser.add_argument('--runs-dir', type=Path)
    parser.add_argument('--campaigns-dir', type=Path)
    parser.add_argument('--evaluations-dir', type=Path)
    args = parser.parse_args(argv)
    if args.port == args.api_port or args.ready_timeout <= 0:
        parser.error('use portas distintas e timeout positivo')
    node = tool_version('node', '--version')
    if not node_supported(node):
        parser.error(f'Node exige {NODE_REQUIREMENT}; encontrado {node}')
    tool_version('npm', '--version')
    tool_version('uv', '--version')
    available(args.port)
    available(args.api_port)
    identity = uuid.uuid4().hex
    directory = ROOT / '.ariadne/inspector' / identity
    directory.mkdir(parents=True)
    processes = Processes(directory)
    environment = {**os.environ, 'ARIADNE_INSPECTOR_SESSION': identity,
                   'ARIADNE_INSPECTOR_API_PORT': str(args.api_port)}
    environment.pop('VIRTUAL_ENV', None)
    for option, variable in [('runs_dir', 'ARIADNE_RUNS_DIR'), ('campaigns_dir', 'ARIADNE_CAMPAIGNS_DIR'),
                             ('evaluations_dir', 'ARIADNE_EVALUATIONS_DIR')]:
        value = getattr(args, option)
        if value is not None:
            environment[variable] = str(value.resolve())
    handlers = {}
    def interrupt(*_):
        raise KeyboardInterrupt
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            handlers[sig] = signal.signal(sig, interrupt)
        lock_hash = hashlib.sha256((INSPECTOR / 'package-lock.json').read_bytes()).hexdigest()
        stamp = ROOT / '.ariadne/inspector/dependencies.sha256'
        if not (INSPECTOR / 'node_modules/.bin/vite').is_file() or not stamp.is_file() or stamp.read_text() != lock_hash:
            print(f'Preparando frontend com npm ci. Logs: {directory}', flush=True)
            install = processes.start(['npm', 'ci', '--no-audit', '--no-fund'], 'install', cwd=INSPECTOR, env=environment)
            if install.wait(timeout=300) != 0:
                raise RuntimeError(f'npm ci falhou; consulte {directory / "install.log"}')
            processes.children.remove(('install', install))
            stamp.write_text(lock_hash)
        processes.start(['uv', 'run', '--locked', '--project', str(INSPECTOR / 'api'),
                         'uvicorn', 'app:app', '--app-dir', str(INSPECTOR / 'api'),
                         '--host', '127.0.0.1', '--port', str(args.api_port)], 'api', env=environment)
        processes.start(['npm', 'run', 'dev', '--', '--port', str(args.port), '--strictPort'],
                        'frontend', cwd=INSPECTOR, env=environment)
        api_url = f'http://127.0.0.1:{args.api_port}/api/health'
        url = f'http://127.0.0.1:{args.port}'
        print(f'Aguardando API e interface. Logs: {directory}', flush=True)
        deadline = time.monotonic() + args.ready_timeout
        while not (ready(api_url, identity, api=True) and ready(url, identity)):
            processes.check()
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Inspector não ficou pronto; consulte {directory}')
            time.sleep(.2)
        processes.check()
        print(f'Inspector pronto: {url}\nCtrl+C encerra API e interface. Logs: {directory}', flush=True)
        while True:
            processes.check()
            time.sleep(.5)
    except KeyboardInterrupt:
        print('\nEncerrando Inspector…', flush=True)
        return 0
    finally:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            processes.stop()
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(f'Erro ao abrir Inspector: {error}')
