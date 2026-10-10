"""Dados versionados do estudo; carregamento sem efeitos de execução."""
import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


def load_world():
    return json.loads((DIRECTORY / "world.json").read_text())


def load_cases():
    return json.loads((DIRECTORY / "cases.json").read_text())


def load_case(identifier):
    for case in load_cases():
        if case["id"] == identifier:
            return case
    raise ValueError(f"unknown logistics case: {identifier}")
