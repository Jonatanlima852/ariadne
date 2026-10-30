"""CLI instalada como ariadne; o checkout também oferece ./ariadne."""

import argparse
import os
from pathlib import Path
import signal
import sys

from ariadne_sdk.execution import load_scenario, run_experiment


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv=None):
    runs_dir = Path(os.environ["ARIADNE_RUNS_DIR"]) if os.getenv("ARIADNE_RUNS_DIR") else None
    parser = argparse.ArgumentParser(description="Execute um experimento Python pelo Ariadne Runtime, em contêineres Docker.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="executa serviços e agentes em contêineres e aplica o cenário")
    run.add_argument("file", type=Path)
    run.add_argument("--output", type=Path, default=runs_dir, help="pasta de evidências; padrão: runs/ ao lado do scenario.py nos estudos, senão .ariadne/runs")
    run.add_argument("--repeat", type=positive, default=1, help="repete o cenário, preservando cada amostra bruta")
    run.add_argument("--ready-timeout", type=positive, default=60)
    run.add_argument("--timeout", type=positive, default=60, help="limite do RPC por amostra; não altera limites do workflow")
    check = commands.add_parser("check", help="valida a descrição Python sem iniciar contêineres")
    check.add_argument("file", type=Path)
    for command in ("status", "logs", "stop"):
        inspect = commands.add_parser(command, help={
            "status": "estado salvo de uma execução", "logs": "logs salvos de uma execução",
            "stop": "remove contêineres que uma execução interrompida tenha deixado"}[command])
        inspect.add_argument("identifier", nargs="?", default="latest")
        inspect.add_argument("--output", type=Path, default=runs_dir)
        if command == "logs":
            inspect.add_argument("--tail", type=positive, default=100)
    campaign = commands.add_parser("campaign", help="coleta uma matriz de experimentos sem avaliar resultados")
    campaign.add_argument("file", type=Path)
    campaign.add_argument("--output", type=Path, default=Path(".ariadne/campaigns"))
    viewer = commands.add_parser("viewer", help="abre o Mission Viewer com as missões gravadas em .ariadne e nos estudos")
    viewer.add_argument("--root", action="append", type=Path, help="pasta com missões (repetível)")
    viewer.add_argument("--port", type=positive, default=4180)
    viewer.add_argument("--no-browser", action="store_true")
    commands.add_parser("help", help="mostra os comandos disponíveis")
    verify = commands.add_parser("verify", help="verifica SDK, runtime, estudos e ferramentas do checkout")
    verify.add_argument("--unit-only", action="store_true")
    doctor = commands.add_parser("doctor", help="confere Python, SDK, Docker, Compose e destino das evidências")
    doctor.add_argument("--file", type=Path, help="valida também uma descrição Python (importa o arquivo)")
    doctor.add_argument("--output", type=Path, default=runs_dir)
    doctor.add_argument("--llm", action="store_true", help="confere extra LLM e presença de credencial, sem chamada externa")
    supplied = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(supplied or ["help"])

    def interrupt(*_):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.command == "viewer":
            root = Path(os.getenv("ARIADNE_ROOT", Path(__file__).resolve().parents[4]))
            script = root / "tools/mission-viewer/serve.py"
            if not script.is_file():
                raise ValueError("viewer requires a checkout; configure ARIADNE_ROOT")
            options = ["--port", str(args.port)] + (["--no-browser"] if args.no_browser else [])
            for folder in args.root or []:
                options.extend(["--root", str(folder.resolve())])
            os.chdir(root)
            os.execv(sys.executable, [sys.executable, str(script), *options])
        if args.command == "doctor":
            from ariadne_sdk.doctor import diagnose
            return diagnose(output=args.output, source=args.file, llm=args.llm)
        if args.command == "verify":
            root = Path(os.getenv("ARIADNE_ROOT", Path(__file__).resolve().parents[4]))
            script = root / "tools/verify.py"
            if not script.is_file():
                raise ValueError("verify requires a checkout; configure ARIADNE_ROOT")
            options = ["--unit-only"] if args.unit_only else []
            os.execv(sys.executable, [sys.executable, str(script), *options])
        if args.command == "help":
            parser.print_help()
            return 0
        if args.command == "campaign":
            from ariadne_sdk.campaign import load_campaign, run_campaign
            _, summary = run_campaign(load_campaign(args.file), output_root=args.output)
            return {"COMPLETED": 0, "CANCELLED": 130}.get(summary["status"], 1)
        if args.command in ("status", "logs", "stop"):
            from ariadne_sdk.runs import print_logs, print_status, read_summary, resolve_run
            directory = resolve_run(args.identifier, args.output)
            if args.command == "stop":
                from ariadne_sdk.compose import Compose
                from ariadne_sdk.evidence import write_json
                summary = read_summary(directory)
                if summary.get("environment") == "stopped":
                    print("Ambiente já encerrado; resultados preservados.")
                    return 0
                if Compose(directory / "logs", directory.name.lower()).down() != 0:
                    raise ValueError(f"não foi possível remover os contêineres; veja {directory / 'logs' / 'compose.log'}")
                summary["environment"] = "stopped"
                write_json(directory / "summary.json", summary)
                print(f"Contêineres removidos; resultados preservados em {directory}")
            elif args.command == "status":
                print_status(directory)
            else:
                print_logs(directory, args.tail)
            return 0
        if args.command == "check":
            scenario = load_scenario(args.file)
            shape = "1 missão" if scenario.mission is not None else f"{len(scenario.tasks)} etapas"
            print(f"Descrição válida: {scenario.name}; {len(scenario.agents)} agentes; {shape}")
            return 0
        _, summary = run_experiment(
            args.file, output_root=args.output, ready_timeout=args.ready_timeout,
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
