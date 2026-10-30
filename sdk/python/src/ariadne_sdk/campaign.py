"""Coleta genérica de execuções isoladas; sem métricas ou gráficos de domínio."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import product
import os
from pathlib import Path
import runpy
import signal
import sys
import uuid

from ariadne_sdk.compose import repository_root
from ariadne_sdk.evidence import utc_now, write_json
from ariadne_sdk.execution import import_roots, run_experiment


@dataclass(frozen=True)
class Campaign:
    experiment: str | Path
    matrix: dict[str, list[str]] = field(default_factory=dict)
    repeat: int = 1
    name: str = "campaign"
    metadata: dict = field(default_factory=dict)
    # Limite do RPC de cada amostra, em segundos; None usa o padrão do executor (60).
    timeout: int | None = None

    def variants(self):
        if isinstance(self.repeat, bool) or not isinstance(self.repeat, int) or self.repeat < 1:
            raise ValueError("campaign repeat must be a positive integer")
        if any(not isinstance(key, str) or not key or '=' in key or '\0' in key for key in self.matrix):
            raise ValueError("matrix keys must be environment variable names")
        for values in self.matrix.values():
            if not values or any(not isinstance(value, str) or '\0' in value for value in values):
                raise ValueError("matrix dimensions require non-empty lists of strings")
            if len(set(values)) != len(values):
                raise ValueError("matrix values must be distinct")
        return [dict(zip(self.matrix, values)) for values in product(*self.matrix.values())]


def load_campaign(source):
    source = Path(source).resolve(strict=True)
    previous_path = sys.path[:]
    try:
        sys.path[:0] = import_roots(source)
        declaration = runpy.run_path(str(source), run_name="__ariadne_campaign__").get("campaign")
    finally:
        sys.path[:] = previous_path
    if not isinstance(declaration, Campaign):
        raise ValueError("declare campaign = Campaign(experiment=..., matrix=...)")
    declaration.variants()
    experiment = Path(declaration.experiment)
    if not experiment.is_absolute():
        experiment = source.parent / experiment
    if declaration.timeout is not None and (isinstance(declaration.timeout, bool) or not isinstance(declaration.timeout, int) or declaration.timeout <= 0):
        raise ValueError("campaign timeout must be a positive integer of seconds")
    return Campaign(experiment.resolve(strict=True), declaration.matrix, declaration.repeat,
                    declaration.name, declaration.metadata, declaration.timeout)


@contextmanager
def environment(values):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def default_output(source):
    """Cenários do repositório gravam em ``campaigns/`` ao lado do ``scenario.py``; os demais em ``.ariadne/campaigns``."""
    root = repository_root()
    if Path(source).resolve().is_relative_to(root / "studies" / "scenarios"):
        return Path(source).resolve().parent / "campaigns"
    return root / ".ariadne" / "campaigns"


def run_campaign(campaign, *, output_root=None, runner=None, timeout=None):
    variants = campaign.variants()
    source = Path(campaign.experiment).resolve(strict=True)
    directory = (Path(output_root).resolve() if output_root else default_output(source)) / ('campaign-' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    manifest = {"schema_version": 2, "name": campaign.name, "metadata": campaign.metadata,
                "experiment": str(source), "created_at": utc_now(), "matrix": campaign.matrix,
                "repetitions": campaign.repeat, "planned_observations": len(variants) * campaign.repeat,
                "rpc_timeout_seconds": timeout or campaign.timeout or 60,
                "status": "RUNNING", "runs": []}
    def save():
        write_json(directory / 'campaign.json', manifest)
    def interrupt(*_):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupt)
    runner = runner or run_experiment
    try:
        save()
        for repetition in range(1, campaign.repeat + 1):
            for parameters in variants:
                execution_id = 'ariadne-' + uuid.uuid4().hex
                entry = {"directory": f"runs/{execution_id}", "repetition": repetition,
                         "parameters": parameters, "status": "RUNNING"}
                manifest['runs'].append(entry)
                save()
                try:
                    with environment(parameters):
                        options = {"task_timeout": timeout or campaign.timeout} if (timeout or campaign.timeout) else {}
                        _, summary = runner(source, output_root=directory / 'runs', execution_id=execution_id, **options)
                    entry['status'] = summary['status']
                    if summary['status'] == 'CANCELLED':
                        raise KeyboardInterrupt
                except KeyboardInterrupt:
                    entry['status'] = 'CANCELLED'
                    raise
                except Exception as error:
                    entry.update(status='FAILED', error=str(error))
                finally:
                    save()
        manifest['status'] = 'COMPLETED' if all(r['status'] == 'COMPLETED' for r in manifest['runs']) else 'FAILED'
    except KeyboardInterrupt:
        manifest['status'] = 'CANCELLED'
    finally:
        signal.signal(signal.SIGTERM, previous)
        manifest['completed_at'] = utc_now()
        save()
    print(f"Campanha: {directory}\nEstado: {manifest['status']}")
    return directory, manifest
