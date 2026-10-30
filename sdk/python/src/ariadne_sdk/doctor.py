"""Diagnóstico sem instalar dependências, construir imagens ou iniciar contêineres."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


COMPOSE_REQUIREMENT = (2, 24, 4)


def version_tuple(value):
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        raise ValueError(f"versão não reconhecida: {value}")
    return tuple(int(part or 0) for part in match.groups())


def compose_supported(value):
    return version_tuple(value) >= COMPOSE_REQUIREMENT


def tool_version(tool, *arguments):
    if not shutil.which(tool):
        raise ValueError(f"{tool} não encontrado no PATH")
    return subprocess.check_output([tool, *arguments], text=True, stderr=subprocess.STDOUT, timeout=20).strip()


def writable_destination(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)


def diagnose(*, output=".ariadne/runs", source=None, llm=False):
    checks = []

    def check(label, operation):
        try:
            detail = operation()
            checks.append((label, True, detail))
        except Exception as error:
            checks.append((label, False, str(error)))

    def require(condition, message, success):
        if not condition:
            raise ValueError(message)
        return success

    check("Python", lambda: require(sys.version_info >= (3, 11), "use Python >=3.11", sys.version.split()[0]))
    for package in ("grpc", "google.protobuf"):
        check(package, lambda package=package: require(
            importlib.util.find_spec(package) is not None,
            "prepare o SDK com uv sync --project sdk/python", "disponível"))
    check("Docker", lambda: tool_version("docker", "version", "--format", "{{.Server.Version}}"))

    def compose():
        installed = tool_version("docker", "compose", "version", "--short")
        return require(compose_supported(installed),
                       f"use Docker Compose >={'.'.join(map(str, COMPOSE_REQUIREMENT))}; encontrado {installed}", installed)
    check("Docker Compose", compose)
    check("Destino de evidências", lambda: require(writable_destination(output),
          f"diretório sem acesso de escrita ou caminho bloqueado: {output}", str(Path(output).resolve())))
    if source is not None:
        def description():
            from ariadne_sdk.execution import load_scenario
            scenario = load_scenario(source)
            shape = "1 missão" if scenario.mission is not None else f"{len(scenario.tasks)} etapas"
            return f"{scenario.name}: {len(scenario.agents)} agentes, {shape}"
        check("Descrição", description)
    if llm:
        for package in ("openai", "pydantic"):
            check(package, lambda package=package: require(
                importlib.util.find_spec(package) is not None,
                "use ARIADNE_SDK_EXTRAS=llm ou instale ariadne-sdk[llm]", "disponível"))
        check("Credencial LLM", lambda: require(bool(os.getenv("OPENAI_API_KEY", "").strip()),
              "exporte OPENAI_API_KEY no terminal; o executor repassa a variável aos contêineres e não lê .env",
              "presente (não validada no provedor)"))
    for label, ok, detail in checks:
        print(f"{'OK' if ok else 'FALHA'} · {label}: {detail}")
    print("Diagnóstico concluído. Não constrói imagens nem verifica rede ou acesso ao modelo.")
    return 0 if all(ok for _, ok, _ in checks) else 1
