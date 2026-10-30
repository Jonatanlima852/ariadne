"""Proveniência da avaliação logística offline, usando somente a biblioteca padrão."""
import hashlib
from pathlib import Path
import subprocess
import sys


def analysis_provenance(evaluator, sources, modules):
    def record(path):
        path = Path(path).resolve(strict=True)
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    evaluator = Path(evaluator).resolve()
    try:
        def git(*args):
            return subprocess.check_output(['git', '-C', str(evaluator.parent), *args],
                                           text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
        revision = git('rev-parse', 'HEAD')
        dirty = bool(git('status', '--porcelain'))
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    return {'schema_version': 1, 'python': sys.version, 'git_revision': revision, 'git_dirty': dirty,
            'evaluator_files': [record(p) for p in sorted({evaluator, Path(__file__).resolve(),
                                                        *(Path(module).resolve() for module in modules)})],
            'inputs': [record(directory / name) for directory in sources
                       for name in ('manifest.json', 'results.jsonl') if (directory / name).is_file()]}
