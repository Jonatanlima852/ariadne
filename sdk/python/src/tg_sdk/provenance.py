"""Proveniência local: versões e hashes, sem ler credenciais ou ambiente."""
import hashlib
from importlib import metadata
from pathlib import Path
import subprocess
import sys


def file_record(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.name == '.env' or path.name.startswith('.env.'):
        raise ValueError(f"artifact must be a regular, non-credential file: {path}")
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def git_state(path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(path), *args], text=True,
                                       stderr=subprocess.DEVNULL, timeout=10).strip()
    try:
        root = git('rev-parse', '--show-toplevel')
        status = git('status', '--porcelain', '--untracked-files=normal')
        return {'root': root, 'revision': git('rev-parse', 'HEAD'),
                'dirty': bool(status), 'changes': status.splitlines()}
    except (OSError, subprocess.SubprocessError):
        return {'root': None, 'revision': None, 'dirty': None, 'changes': []}


def capture(source, artifacts=()):
    source = Path(source).resolve(strict=True)
    git = git_state(source.parent)
    paths = {source}
    for artifact in artifacts:
        path = Path(artifact)
        paths.add((path if path.is_absolute() else source.parent / path).resolve(strict=True))
    if git['root']:
        root = Path(git['root'])
        for module in list(sys.modules.values()):
            filename = getattr(module, '__file__', None)
            if filename:
                path = Path(filename).resolve()
                if path.suffix == '.py' and path.is_relative_to(root) and not any(part in path.parts for part in ('.venv', '.tg', 'site-packages')):
                    paths.add(path)
        for relative in ('runtime/go.mod', 'runtime/go.sum'):
            if (root / relative).is_file():
                paths.add(root / relative)
    project = Path(__file__).resolve().parents[2]
    for filename in ('pyproject.toml', 'uv.lock'):
        if (project / filename).is_file():
            paths.add(project / filename)
    return {'schema_version': 1, 'git': git, 'python': sys.version,
            'packages': sorted(({'name': d.metadata['Name'], 'version': d.version}
                                for d in metadata.distributions()), key=lambda item: item['name'].lower()),
            'files': [file_record(path) for path in sorted(paths)],
            'scope': 'source, loaded repository Python modules, declared artifacts and runtime/SDK dependency manifests'}
