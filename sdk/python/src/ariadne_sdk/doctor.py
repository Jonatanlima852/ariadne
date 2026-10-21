"""Diagnóstico local sem instalar dependências, compilar ou iniciar serviços."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


NODE_REQUIREMENT = "^20.19.0 || >=22.12.0"


def version_tuple(value):
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        raise ValueError(f"versão não reconhecida: {value}")
    return tuple(int(part or 0) for part in match.groups())


def node_supported(value):
    version = version_tuple(value)
    return (version[0] == 20 and version >= (20, 19, 0)) or version >= (22, 12, 0)


def tool_version(tool, *arguments):
    if not shutil.which(tool):
        raise ValueError(f"{tool} não encontrado no PATH")
    return subprocess.check_output(
        [tool, *arguments], text=True, stderr=subprocess.STDOUT, timeout=10,
        env={**os.environ, "GOTOOLCHAIN": "local"},
    ).strip()


def writable_destination(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)


def diagnose(*, runtime_source=None, runtime_dir=None, output=".ariadne/runs",
             source=None, llm=False, inspector=False):
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

    if runtime_dir is not None:
        for service in ("registry", "orchestrator", "messaging"):
            binary = Path(runtime_dir) / f"ariadne-{service}"
            check(service, lambda binary=binary: require(
                binary.is_file() and os.access(binary, os.X_OK),
                f"executável ausente: {binary}; prepare o runtime ou ajuste --runtime-dir", str(binary)))
    else:
        def go():
            if runtime_source is None:
                raise ValueError("informe --runtime-dir ou --runtime-source; no checkout use ./ariadne")
            module = Path(runtime_source) / "go.mod"
            match = re.search(r"^go\s+(\S+)", module.read_text(), re.MULTILINE)
            if not match:
                raise ValueError(f"versão Go ausente em {module}")
            installed = tool_version("go", "version")
            return require(version_tuple(installed) >= version_tuple(match[1]),
                           f"instale Go >={match[1]}; encontrado {installed}", installed)
        check("Runtime Go", go)

    check("Destino de evidências", lambda: require(writable_destination(output),
          f"diretório sem acesso de escrita ou caminho bloqueado: {output}", str(Path(output).resolve())))
    if source is not None:
        def description():
            from ariadne_sdk.execution import load_scenario
            scenario = load_scenario(source)
            return f"{scenario.name}: {len(scenario.agents)} agentes, {len(scenario.tasks)} etapas"
        check("Descrição", description)
    if llm:
        for package in ("openai", "pydantic"):
            check(package, lambda package=package: require(
                importlib.util.find_spec(package) is not None,
                "use ARIADNE_SDK_EXTRAS=llm ou instale ariadne-sdk[llm]", "disponível"))
        check("Credencial LLM", lambda: require(bool(os.getenv("OPENAI_API_KEY", "").strip()),
              "exporte OPENAI_API_KEY no terminal; o executor local não lê .env", "presente (não validada no provedor)"))
    if inspector:
        def node():
            installed = tool_version("node", "--version")
            return require(node_supported(installed), f"use Node {NODE_REQUIREMENT}; encontrado {installed}", installed)
        check("Node", node)
        check("npm", lambda: tool_version("npm", "--version"))
        check("uv para API do Inspector", lambda: tool_version("uv", "--version"))
    for label, ok, detail in checks:
        print(f"{'OK' if ok else 'FALHA'} · {label}: {detail}")
    print("Diagnóstico local concluído. Não verifica rede, acesso ao modelo ou prontidão dos serviços.")
    return 0 if all(ok for _, ok, _ in checks) else 1
