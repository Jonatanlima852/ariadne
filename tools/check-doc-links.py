"""Confere destinos locais de links inline na documentação pública versionada.

Não consulta URLs externas nem valida âncoras Markdown.
"""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '*.md'], cwd=ROOT).decode().split('\0')
    failures = []
    checked = 0
    for name in sorted(set(names)):
        if not name or (name != 'README.md' and Path(name).parts[0] not in
                        {'docs', 'examples', 'sdk', 'studies', 'tools', 'proto'}):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        fenced = False
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.lstrip().startswith(('```', '~~~')):
                fenced = not fenced
                continue
            if fenced:
                continue
            for target in re.findall(r'\]\(([^)]+)\)', line):
                target = target.split(' "', 1)[0].strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                checked += 1
                if not (path.parent / unquote(parsed.path)).exists():
                    failures.append(f'{name}:{number}: {target}')
    for failure in failures:
        print(failure)
    print(f'Links locais: {checked} conferidos, {len(failures)} ausentes.')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
