"""Campanha: o cenário para vários K, com repetições, seguido da análise.

Para cada K em ``--workers`` executa ``python -m ariadne_sdk run
studies/scenarios/fanout/scenario.py --repeat R`` com ``FANOUT_WORKERS=K`` (e
as demais variáveis do estudo), guarda o diretório de evidências de cada
execução e, ao final, chama ``analysis.py`` sobre todos eles para produzir a
tabela e a figura de speedup.

Uso, da raiz do repositório (cada execução sobe seus contêineres):

    uv run --project sdk/python python -m studies.scenarios.fanout.campaign \
        --workers 1 2 4 8 --repeat 3 --flaky 0 --output .ariadne/fanout/<nome>

O contador lento fica desligado por padrão na varredura de K para que o
speedup meça só o paralelismo; ``--flaky 1`` inclui as reatribuições.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCENARIO = Path(__file__).resolve().parent / "scenario.py"
_EVIDENCE = re.compile(r"^Evidências: (.+)$", re.MULTILINE)


def run_once(workers, *, repeat, shards, flaky, output, extra_env=None, timeout=120):
    environment = {**os.environ, "FANOUT_WORKERS": str(workers), "FANOUT_SHARDS": str(shards),
                   "FANOUT_FLAKY": "1" if flaky else "0", **(extra_env or {})}
    command = [sys.executable, "-m", "ariadne_sdk", "run", str(SCENARIO),
               "--output", str(output), "--repeat", str(repeat), "--timeout", str(timeout)]
    print(f"> FANOUT_WORKERS={workers} FANOUT_SHARDS={shards} FANOUT_FLAKY={environment['FANOUT_FLAKY']} "
          + " ".join(command[1:]), flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
    sys.stdout.write(completed.stdout)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise RuntimeError(f"run failed for K={workers} (exit {completed.returncode})")
    match = _EVIDENCE.search(completed.stdout)
    if not match:
        raise RuntimeError("could not find the evidence directory in the run output")
    return Path(match.group(1).strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--flaky", type=int, choices=(0, 1), default=0)
    parser.add_argument("--work-ms", type=int, default=None, help="FANOUT_WORK_MS")
    parser.add_argument("--step-deadline-ms", type=int, default=None, help="FANOUT_STEP_DEADLINE_MS")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=120, help="limite do RPC por amostra, em segundos")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)
    output = args.output or ROOT / ".ariadne/fanout" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=True)
    extra = {}
    if args.work_ms is not None:
        extra["FANOUT_WORK_MS"] = str(args.work_ms)
    if args.step_deadline_ms is not None:
        extra["FANOUT_STEP_DEADLINE_MS"] = str(args.step_deadline_ms)
    runs = [run_once(workers, repeat=args.repeat, shards=args.shards, flaky=bool(args.flaky),
                     output=output / "runs", extra_env=extra,
                     timeout=args.timeout)
            for workers in args.workers]
    from studies.scenarios.fanout.analysis import analyze_runs, write_outputs, markdown_report
    report = analyze_runs(runs)
    written = write_outputs(report, output / "analysis", figures=not args.no_figures)
    print(markdown_report(report))
    print("Campanha: " + str(output))
    print("Arquivos: " + ", ".join(str(path) for path in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
