"""Consulta offline das evidências de uma execução."""
from collections import deque
import json
from pathlib import Path
import re

from ariadne_sdk.compose import repository_root


def search_roots(root=None):
    """Onde procurar um ID: a raiz pedida, ``.ariadne/runs`` e o ``runs/`` de cada cenário."""
    repository = repository_root()
    roots = [Path(root).resolve()] if root else []
    roots.append(repository / ".ariadne" / "runs")
    roots.extend(sorted(repository.glob("studies/scenarios/**/runs")))
    return roots


def resolve_run(identifier, root=None):
    if identifier == "latest":
        latest = repository_root() / ".ariadne" / "latest"
        if not latest.is_file():
            raise ValueError("nenhuma execução registrada")
        identifier = latest.read_text().strip()
    candidate = Path(identifier)
    if candidate.is_dir():
        directory = candidate.resolve()
    else:
        if not re.fullmatch(r"ariadne-[A-Za-z0-9-]+", identifier):
            raise ValueError("identificador de execução inválido")
        directory = next((base / identifier for base in search_roots(root) if (base / identifier).is_dir()), None)
        if directory is None:
            raise ValueError(f"execução não encontrada: {identifier}")
    if not (directory / "summary.json").is_file():
        raise ValueError(f"execução não encontrada: {identifier}")
    return directory


def read_summary(directory):
    return json.loads((directory / "summary.json").read_text(encoding="utf-8"))


def print_status(directory):
    summary = read_summary(directory)
    print(f"Execução: {directory.name}\nBackend: {summary.get('backend', 'unknown')}")
    for label, key in (("Cenário", "scenario"), ("Estado", "status"), ("Ambiente", "environment")):
        print(f"{label}: {summary.get(key, 'unknown')}")
    if summary.get("error"):
        print(f"Erro: {summary['error']}")
    print(f"Resultados: {directory}")


def print_logs(directory, tail=100):
    files = [path for folder in (directory, directory / "logs") if folder.is_dir()
             for path in sorted(folder.iterdir()) if path.is_file() and path.suffix in (".log", ".jsonl")]
    for path in files:
        print(f"\n{path.relative_to(directory)}")
        with path.open(encoding="utf-8", errors="replace") as stream:
            print("".join(deque(stream, maxlen=tail)), end="")
