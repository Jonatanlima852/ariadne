"""CLI instalada como tg; o checkout também oferece ./tg run."""

import argparse
import os
from pathlib import Path
import signal

from tg_sdk.execution import load_scenario, run_experiment


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Execute um experimento Python pelo TG Runtime.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="executa agentes e cenário em processos locais")
    run.add_argument("file", type=Path)
    binaries = run.add_mutually_exclusive_group()
    binaries.add_argument("--runtime-dir", type=Path, default=os.getenv("TG_RUNTIME_DIR"))
    binaries.add_argument("--runtime-source", type=Path, help="compila os serviços deste módulo Go")
    run.add_argument("--output", type=Path, default=Path(os.getenv("TG_RUNS_DIR", ".tg/runs")))
    run.add_argument("--repeat", type=positive, default=1, help="repete o cenário, preservando cada amostra bruta")
    run.add_argument("--ready-timeout", type=positive, default=30)
    run.add_argument("--timeout", type=positive, default=60, help="limite do RPC por amostra; não altera limites do workflow")
    check = commands.add_parser("check", help="valida a descrição Python sem iniciar processos")
    check.add_argument("file", type=Path)
    for command in ("status", "logs"):
        inspect = commands.add_parser(command, help="consulta evidências locais ou Docker salvas")
        inspect.add_argument("identifier", nargs="?", default="latest")
        inspect.add_argument("--output", type=Path, default=Path(os.getenv("TG_RUNS_DIR", ".tg/runs")))
        if command == "logs":
            inspect.add_argument("--tail", type=positive, default=100)
    args = parser.parse_args(argv)

    def interrupt(*_):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.command in ("status", "logs"):
            from tg_sdk.runs import print_logs, print_status, resolve_run
            directory = resolve_run(args.identifier, args.output)
            print_status(directory) if args.command == "status" else print_logs(directory, args.tail)
            return 0
        if args.command == "check":
            scenario = load_scenario(args.file)
            print(f"Descrição válida: {scenario.name}; {len(scenario.agents)} agentes; {len(scenario.tasks)} etapas")
            return 0
        _, summary = run_experiment(
            args.file, output_root=args.output, runtime_dir=args.runtime_dir,
            runtime_source=args.runtime_source or (os.getenv("TG_RUNTIME_SOURCE") if args.runtime_dir is None else None),
            ready_timeout=args.ready_timeout,
            task_timeout=args.timeout, repeat=args.repeat,
        )
        return {"COMPLETED": 0, "CANCELLED": 130}.get(summary["status"], 1)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        parser.exit(1, f"Erro: {error}\n")
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
