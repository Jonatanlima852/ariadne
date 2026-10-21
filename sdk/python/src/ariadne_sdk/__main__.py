"""CLI instalada como ariadne; o checkout também oferece ./ariadne run."""

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
    parser = argparse.ArgumentParser(description="Execute um experimento Python pelo Ariadne Runtime.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="executa agentes e cenário em processos locais")
    run.add_argument("file", type=Path)
    binaries = run.add_mutually_exclusive_group()
    binaries.add_argument("--runtime-dir", type=Path, default=os.getenv("ARIADNE_RUNTIME_DIR"))
    binaries.add_argument("--runtime-source", type=Path, help="compila os serviços deste módulo Go")
    run.add_argument("--output", type=Path, default=Path(os.getenv("ARIADNE_RUNS_DIR", ".ariadne/runs")))
    run.add_argument("--repeat", type=positive, default=1, help="repete o cenário, preservando cada amostra bruta")
    run.add_argument("--ready-timeout", type=positive, default=30)
    run.add_argument("--timeout", type=positive, default=60, help="limite do RPC por amostra; não altera limites do workflow")
    check = commands.add_parser("check", help="valida a descrição Python sem iniciar processos")
    check.add_argument("file", type=Path)
    for command in ("status", "logs"):
        inspect = commands.add_parser(command, help="consulta evidências locais ou Docker salvas")
        inspect.add_argument("identifier", nargs="?", default="latest")
        inspect.add_argument("--output", type=Path, default=Path(os.getenv("ARIADNE_RUNS_DIR", ".ariadne/runs")))
        if command == "logs":
            inspect.add_argument("--tail", type=positive, default=100)
    campaign = commands.add_parser("campaign", help="coleta uma matriz de experimentos sem avaliar resultados")
    campaign.add_argument("file", type=Path)
    campaign.add_argument("--output", type=Path, default=Path(".ariadne/campaigns"))
    campaign.add_argument("--runtime-dir", type=Path, default=os.getenv("ARIADNE_RUNTIME_DIR"))
    campaign.add_argument("--runtime-source", type=Path, default=os.getenv("ARIADNE_RUNTIME_SOURCE"))
    from ariadne_sdk.docker import SCENARIOS
    commands.add_parser("help", help="mostra os comandos disponíveis")
    inspector = commands.add_parser("inspect", help="inicia API e interface local para explorar evidências")
    inspector.add_argument('--port', type=positive, default=4173)
    inspector.add_argument('--api-port', type=positive, default=8787)
    inspector.add_argument('--ready-timeout', type=positive, default=90)
    for option in ('runs-dir', 'campaigns-dir', 'evaluations-dir'):
        inspector.add_argument('--' + option, type=Path)
    verify = commands.add_parser("verify", help="verifica SDK, runtime, estudos e ferramentas do checkout")
    verify.add_argument("--unit-only", action="store_true")
    verify.add_argument("--no-inspector", action="store_true")
    doctor = commands.add_parser("doctor", help="verifica Docker ou requisitos locais com --local")
    doctor.add_argument("scenario", nargs="?", choices=SCENARIOS)
    doctor.add_argument("--local", action="store_true", help="diagnostica o backend de processos locais")
    doctor.add_argument("--file", type=Path, help="valida também uma descrição Python (importa o arquivo)")
    doctor_binaries = doctor.add_mutually_exclusive_group()
    doctor_binaries.add_argument("--runtime-dir", type=Path)
    doctor_binaries.add_argument("--runtime-source", type=Path)
    doctor.add_argument("--output", type=Path)
    doctor.add_argument("--llm", action="store_true", help="confere extra LLM e presença de credencial, sem chamada externa")
    doctor.add_argument("--inspector", action="store_true", help="confere Node, npm e uv")
    demo = commands.add_parser("demo", help="executa o exemplo Docker básico")
    demo.add_argument("--keep", action="store_true")
    scenario = commands.add_parser("scenario", help="lista ou executa exemplos Docker")
    scenario.add_argument("scenario", nargs="?", choices=SCENARIOS)
    scenario.add_argument("--keep", action="store_true")
    stop = commands.add_parser("stop", help="encerra uma execução Docker ou consulta se já terminou")
    stop.add_argument("identifier", nargs="?", default="latest")
    stop.add_argument("--output", type=Path, default=Path(os.getenv("ARIADNE_RUNS_DIR", ".ariadne/runs")))
    supplied = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(supplied or ["help"])
    if args.command == "doctor":
        if args.local and args.scenario:
            parser.error("doctor --local não aceita cenário Docker; use --file caminho.py")
        if not args.local and any((args.file, args.runtime_dir, args.runtime_source, args.output, args.llm, args.inspector)):
            parser.error("as opções de diagnóstico local exigem --local")

    def interrupt(*_):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.command == 'inspect':
            root = Path(os.getenv('ARIADNE_ROOT', Path(__file__).resolve().parents[4]))
            script = root / 'tools/inspector/serve.py'
            if not script.is_file():
                raise ValueError('inspect exige o checkout; configure ARIADNE_ROOT')
            options = ['--port', str(args.port), '--api-port', str(args.api_port),
                       '--ready-timeout', str(args.ready_timeout)]
            for option in ('runs-dir', 'campaigns-dir', 'evaluations-dir'):
                value = getattr(args, option.replace('-', '_'))
                if value is not None:
                    options.extend(['--' + option, str(value.resolve())])
            os.execv(sys.executable, [sys.executable, str(script), *options])
        if args.command == "doctor" and args.local:
            from ariadne_sdk.doctor import diagnose
            runtime_dir = args.runtime_dir or (os.getenv("ARIADNE_RUNTIME_DIR") if args.runtime_source is None else None)
            return diagnose(runtime_dir=runtime_dir,
                            runtime_source=args.runtime_source or os.getenv("ARIADNE_RUNTIME_SOURCE"),
                            output=args.output or os.getenv("ARIADNE_RUNS_DIR", ".ariadne/runs"),
                            source=args.file, llm=args.llm, inspector=args.inspector)
        if args.command == "verify":
            root = Path(os.getenv("ARIADNE_ROOT", Path(__file__).resolve().parents[4]))
            script = root / "tools/verify.py"
            if not script.is_file():
                raise ValueError("verify requires a checkout; configure ARIADNE_ROOT")
            options = [flag for flag, enabled in (("--unit-only", args.unit_only), ("--no-inspector", args.no_inspector)) if enabled]
            os.execv(sys.executable, [sys.executable, str(script), *options])
        if args.command == "help":
            parser.print_help()
            return 0
        if args.command in ("doctor", "demo", "scenario"):
            from ariadne_sdk.docker import command, SCENARIOS
            if args.command == "scenario" and args.scenario is None:
                print("Cenários: " + ", ".join(SCENARIOS))
                return 0
            options = [args.scenario or "demo"] if args.command in ("doctor", "scenario") else []
            if getattr(args, "keep", False):
                options.append("--keep")
            command(args.command, *options)
        if args.command == "campaign":
            from ariadne_sdk.campaign import load_campaign, run_campaign
            _, summary = run_campaign(load_campaign(args.file), output_root=args.output,
                                      runtime_dir=args.runtime_dir, runtime_source=args.runtime_source)
            return {"COMPLETED": 0, "CANCELLED": 130}.get(summary["status"], 1)
        if args.command in ("status", "logs", "stop"):
            from ariadne_sdk.runs import print_logs, print_status, resolve_run
            directory = resolve_run(args.identifier, args.output)
            from ariadne_sdk.runs import backend
            environment = (directory / "environment").read_text().strip() if (directory / "environment").is_file() else "unknown"
            if args.command == "stop":
                if environment == "stopped":
                    print("Ambiente já encerrado; resultados preservados.")
                    return 0
                if backend(directory) != "docker":
                    raise ValueError("Para interromper processos locais, use Ctrl+C no supervisor.")
                from ariadne_sdk.docker import command
                command("stop", directory)
            elif args.command == "status":
                print_status(directory)
            else:
                print_logs(directory, args.tail)
                if backend(directory) == "docker" and environment != "stopped":
                    from ariadne_sdk.docker import command
                    sys.stdout.flush()
                    command("logs-live", directory, replace=False)
            return 0
        if args.command == "check":
            scenario = load_scenario(args.file)
            print(f"Descrição válida: {scenario.name}; {len(scenario.agents)} agentes; {len(scenario.tasks)} etapas")
            return 0
        _, summary = run_experiment(
            args.file, output_root=args.output, runtime_dir=args.runtime_dir,
            runtime_source=args.runtime_source or (os.getenv("ARIADNE_RUNTIME_SOURCE") if args.runtime_dir is None else None),
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
