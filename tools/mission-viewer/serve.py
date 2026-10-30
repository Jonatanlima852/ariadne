#!/usr/bin/env python3
"""Serve o Mission Viewer com um índice das missões gravadas em disco (só biblioteca padrão).

Da raiz do repositório: python3 tools/mission-viewer/serve.py [--root PASTA ...] [--port 4180] [--no-browser]
Rotas: / (index.html), /api/runs (índice JSON das missões sob as raízes), /api/file?path=... (restrito às raízes).
"""
import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOTS = ['.ariadne/runs', '.ariadne/logistics-v3', '.ariadne/fanout', '.ariadne/campaigns', 'studies', 'tools/mission-viewer/fixtures']
MAX_DEPTH = 8
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'cache', 'bin', 'agents', 'docker', 'tests', 'domain'}


def _duration_ms(start, end):
    try:
        a, b = (datetime.fromisoformat(str(text).replace('Z', '+00:00')) for text in (start, end))
    except (TypeError, ValueError):
        return None
    return round((b - a).total_seconds() * 1000)


def _read_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def summarize(doc, path):
    """Campos que a lista mostra; o visualizador calcula os mesmos no navegador."""
    if not isinstance(doc, dict) or not isinstance(doc.get('rounds'), list):
        return None
    request = doc.get('request') or {}
    metadata = request.get('metadata') or {}
    context = request.get('context') or {}
    case = context.get('case') if isinstance(context.get('case'), dict) else {}
    entry = {
        'path': path, 'name': os.path.basename(path), 'mission_id': doc.get('mission_id'),
        'status': doc.get('status'), 'goal': request.get('goal') or doc.get('root_task_id') or '',
        'created_at': doc.get('created_at'), 'completed_at': doc.get('completed_at'),
        'duration_ms': _duration_ms(doc.get('created_at'), doc.get('completed_at')),
        'rounds': len(doc['rounds']), 'last_action': (doc['rounds'][-1].get('action') if doc['rounds'] else None),
        'case': metadata.get('case') or case.get('id'), 'suite': metadata.get('suite') or case.get('suite'),
        'configuration': metadata.get('configuration'),
        'scenario': metadata.get('study') or (request.get('trace') or {}).get('correlation_id'),
        'presentation': metadata.get('presentation') if isinstance(metadata.get('presentation'), dict) else None,
    }
    manifest = os.path.join(os.path.dirname(path), 'manifest.json')
    if os.path.isfile(manifest):
        try:
            document = _read_json(manifest)
            entry['scenario'] = scenario_from_source(document.get('source')) or entry['scenario']
            # Rótulos editoriais declarados em Scenario(metadata={'presentation': {...}}).
            presentation = (document.get('metadata') or {}).get('presentation')
            if isinstance(presentation, dict):
                entry['presentation'] = presentation
        except (OSError, ValueError):
            pass
    return entry


def scenario_from_source(source):
    """``.../studies/scenarios/logistics/v3/scenario.py`` vira ``logistics/v3``."""
    if not source:
        return None
    folder = os.path.dirname(source).replace(os.sep, '/')
    marker = '/studies/scenarios/'
    return folder.split(marker, 1)[1] if marker in folder else os.path.basename(folder)


def is_candidate(root, dirpath, name):
    return name.endswith('.json') and (name == 'mission-result.json' or os.path.basename(dirpath) == 'missions'
                                      or os.path.samefile(dirpath, root))


def scan(roots):
    runs = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            depth = os.path.relpath(dirpath, root).count(os.sep) + (dirpath != root)
            dirnames[:] = [] if depth >= MAX_DEPTH else [name for name in dirnames if name not in SKIP_DIRS]
            for name in filenames:
                if not is_candidate(root, dirpath, name):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    entry = summarize(_read_json(path), os.path.relpath(path))
                except (OSError, ValueError):
                    entry = None
                if entry:
                    entry['mtime'] = os.path.getmtime(path)
                    runs.append(entry)
    runs.sort(key=lambda item: (item.get('created_at') or '', item['mtime']), reverse=True)
    return runs


def make_handler(roots):
    real_roots = [os.path.realpath(root) for root in roots]

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=HERE, **kwargs)

        def log_message(self, fmt, *args):  # silencioso, exceto erros
            if len(args) > 1 and str(args[1])[:1] in '45':
                super().log_message(fmt, *args)

        def send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/api/runs':
                return self.send_json(200, {'roots': [os.path.relpath(root) for root in roots], 'runs': scan(roots)})
            if url.path == '/api/file':
                requested = parse_qs(url.query).get('path', [''])[0]
                real = os.path.realpath(requested)
                allowed = any(os.path.commonpath([real, root]) == root for root in real_roots)
                if not allowed or not real.endswith('.json') or not os.path.isfile(real):
                    return self.send_json(403, {'error': 'caminho fora das raízes servidas', 'path': requested})
                try:
                    return self.send_json(200, _read_json(real))
                except ValueError as error:
                    return self.send_json(400, {'error': f'JSON inválido: {error}', 'path': requested})
            return super().do_GET()

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', action='append', help='pasta com missões (repetível); padrão: ' + ', '.join(DEFAULT_ROOTS))
    parser.add_argument('--port', type=int, default=4180)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--no-browser', action='store_true', help='não abrir o navegador')
    args = parser.parse_args(argv)
    roots = [root for root in (args.root or DEFAULT_ROOTS) if os.path.isdir(root)]
    if not roots:
        parser.error('nenhuma raiz existe; rode da raiz do repositório ou passe --root')
    server = ThreadingHTTPServer((args.host, args.port), make_handler(roots))
    url = f'http://{args.host}:{args.port}/'
    print(f'Mission Viewer em {url}  (raízes: {", ".join(roots)}; Ctrl+C para sair)')
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
