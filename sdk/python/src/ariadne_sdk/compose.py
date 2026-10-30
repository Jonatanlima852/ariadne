"""Único backend de execução: cada serviço Go e cada agente em um contêiner.

O arquivo Compose é gerado a partir da declaração e gravado junto às
evidências. O repositório e o diretório da execução são montados nos
contêineres nos mesmos caminhos do host, de modo que ``scenario.py``,
imports, manifesto e arquivos de prontidão usem um caminho só.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

SERVICES = ("registry", "orchestrator", "messaging")
PORTS = {"registry": 50051, "orchestrator": 50052, "messaging": 50053}
AGENT_PORT = 60051
# Repassadas aos agentes sempre que existirem no host; os valores nunca são
# escritos no arquivo Compose nem nas evidências.
FORWARDED = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL", "HEARTBEAT_INTERVAL_SECONDS")
RESERVED = {"REGISTRY_ADDR", "ORCHESTRATOR_ADDR", "MESSAGING_ADDR", "ARIADNE_AGENT_HOST",
            "ARIADNE_AGENT_PORT", "HOME", "PATH", "PYTHONPATH", "PWD"}


def repository_root():
    configured = os.getenv("ARIADNE_ROOT")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[4]


def forwarded_names(scenario):
    names = [name for name in (*FORWARDED, *scenario.environment)
             if name in os.environ and name not in RESERVED]
    return sorted(dict.fromkeys(names))


def compose_document(*, root, directory, source, scenario):
    """Descrição Compose da execução: três serviços Go e um contêiner por agente."""
    user = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else None
    mounts = [f"{root}:{root}:ro", f"{directory}:{directory}"]
    if not source.parent.is_relative_to(root):
        mounts.append(f"{source.parent}:{source.parent}:ro")
    addresses = {name: f"{name}:{port}" for name, port in PORTS.items()}
    services = {}
    for name in SERVICES:
        environment = [f"{name.upper()}_ADDR=:{PORTS[name]}", "ARIADNE_JSON_LOGS=1",
                       f"ARIADNE_READY_FILE={directory}/{name}.ready"]
        if name != "registry":
            environment.append(f"REGISTRY_ADDR={addresses['registry']}")
            evidence = "events.jsonl" if name == "orchestrator" else "message-events.jsonl"
            environment.append(f"EVENTS_PATH={directory}/{evidence}")
        services[name] = {
            "image": f"ariadne-{name}:local",
            "build": {"context": str(root), "dockerfile": f"runtime/services/{name}/Dockerfile"},
            "environment": environment,
            "ports": [f"127.0.0.1::{PORTS[name]}"],
            "volumes": [f"{directory}:{directory}"],
            "depends_on": [] if name == "registry" else ["registry"],
        }
    for index in range(len(scenario.agents)):
        name = f"agent-{index + 1}"
        services[name] = {
            "image": "ariadne-agent:local",
            "build": {"context": str(root / "sdk/python"), "dockerfile": "Dockerfile"},
            "command": [str(source), str(index), addresses["registry"], str(directory)],
            "working_dir": str(root),
            "environment": [
                f"PYTHONPATH={root}/sdk/python/src:{root}", "HOME=/tmp",
                *(f"{service.upper()}_ADDR={address}" for service, address in addresses.items()),
                f"ARIADNE_AGENT_HOST={name}", f"ARIADNE_AGENT_PORT={AGENT_PORT}",
                *forwarded_names(scenario),
            ],
            "volumes": mounts,
            "depends_on": list(SERVICES),
        }
    if user:
        for service in services.values():
            service["user"] = user
    return {"services": services}


class Compose:
    """Executa ``docker compose`` para um projeto exclusivo desta execução."""

    def __init__(self, directory, project, events=None):
        self.directory = Path(directory)
        self.project = project
        self.file = self.directory / "compose.yaml"
        self.log = self.directory / "compose.log"
        self.events = events

    @staticmethod
    def available():
        if shutil.which("docker") is None:
            raise RuntimeError("Docker is required: install Docker with Compose v2 and start the daemon")
        probe = subprocess.run(["docker", "compose", "version", "--short"], capture_output=True, text=True)
        if probe.returncode != 0:
            raise RuntimeError("Docker Compose v2 is not available or the Docker daemon is not running")
        return probe.stdout.strip()

    def write(self, document):
        # JSON é YAML válido; o arquivo fica legível e sem dependência extra.
        self.file.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def command(self, *arguments):
        return ["docker", "compose", "--project-name", self.project, "--file", str(self.file), *arguments]

    def run(self, *arguments, check=True, capture=False, timeout=None):
        if self.events:
            self.events.emit("COMPOSE_COMMAND", arguments=list(arguments))
        with self.log.open("ab") as log:
            log.write(("\n> docker compose " + " ".join(arguments) + "\n").encode())
            log.flush()
            completed = subprocess.run(
                self.command(*arguments), stdout=subprocess.PIPE if capture else log,
                stderr=log, text=capture, check=False, timeout=timeout, env=os.environ,
            )
        if check and completed.returncode:
            raise RuntimeError(f"docker compose {arguments[0]} failed with {completed.returncode}; see compose.log")
        return completed.stdout if capture else completed.returncode

    def build(self):
        self.run("build", "--quiet", timeout=1800)

    def up(self, *services):
        self.run("up", "--detach", "--no-build", "--quiet-pull", *services, timeout=300)

    def port(self, service, port):
        published = self.run("port", service, str(port), capture=True, timeout=30).strip()
        if not published:
            raise RuntimeError(f"{service} has no published port")
        return "127.0.0.1:" + published.rsplit(":", 1)[1]

    def states(self):
        output = self.run("ps", "--all", "--format", "json", capture=True, timeout=30).strip()
        if not output:
            return []
        if output.startswith("["):
            return json.loads(output)
        return [json.loads(line) for line in output.splitlines() if line.strip()]

    def check(self):
        """Falha cedo quando um contêiner da execução já terminou."""
        for item in self.states():
            if item.get("State") == "exited":
                service = item.get("Service") or item.get("Name")
                raise RuntimeError(f"{service} exited with {item.get('ExitCode')}; see {service}.log")

    def images(self):
        # Só lista imagens de contêineres existentes; antes do ``up`` devolve ``null``.
        output = self.run("images", "--format", "json", capture=True, timeout=30).strip()
        records = (json.loads(output) if output.startswith("[") else
                   [json.loads(line) for line in output.splitlines() if line.strip()]) if output else None
        if not records:
            return []
        return [{"container": item.get("ContainerName"), "image": f"{item.get('Repository')}:{item.get('Tag')}", "id": item.get("ID")}
                for item in records]

    def save_logs(self, services):
        """Um ``<serviço>.log`` por contêiner, como os processos locais produziam."""
        for service in services:
            try:
                output = self.run("logs", "--no-color", "--no-log-prefix", service, capture=True, check=False, timeout=60)
            except subprocess.TimeoutExpired:
                output = None
            if output:
                (self.directory / f"{service}.log").write_text(output, encoding="utf-8")

    def down(self):
        return self.run("down", "--volumes", "--remove-orphans", "--timeout", "5", check=False, timeout=120)

    def running(self):
        return [item for item in self.states() if item.get("State") not in (None, "exited")]
