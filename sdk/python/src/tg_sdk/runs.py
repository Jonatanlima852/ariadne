"""Consulta offline das evidências dos backends local e Docker."""
from collections import deque
from pathlib import Path
import re


def resolve_run(identifier, root):
    root = Path(root).resolve()
    if identifier == "latest":
        latest = root.parent / "latest"
        if not latest.is_file():
            raise ValueError("nenhuma execução registrada")
        identifier = latest.read_text().strip()
    candidate = Path(identifier)
    if candidate.is_dir():
        directory = candidate.resolve()
    else:
        if not re.fullmatch(r"tg-[A-Za-z0-9-]+", identifier):
            raise ValueError("identificador de execução inválido")
        directory = root / identifier
    if not (directory / "scenario").is_file() or not (directory / "status").is_file():
        raise ValueError(f"execução não encontrada: {identifier}")
    return directory


def backend(directory):
    return "docker" if (directory / "control.yaml").is_file() else "local-processes"


def print_status(directory):
    print(f"Execução: {directory.name}\nBackend: {backend(directory)}")
    for label, filename in (("Cenário", "scenario"), ("Estado", "status"), ("Ambiente", "environment")):
        path = directory / filename
        print(f"{label}: {path.read_text().strip() if path.is_file() else 'unknown'}")
    print(f"Resultados: {directory}")


def print_logs(directory, tail=100):
    for path in sorted(directory.iterdir()):
        if path.is_file() and not path.is_symlink() and path.suffix in (".log", ".jsonl"):
            print(f"\n{path.name}")
            with path.open(encoding="utf-8", errors="replace") as stream:
                print("".join(deque(stream, maxlen=tail)), end="")
