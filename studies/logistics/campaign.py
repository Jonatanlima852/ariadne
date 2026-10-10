"""Coleta amostras brutas; a avaliação é executada em outro comando."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import uuid

from tg_sdk.execution import run_experiment
from studies.logistics.data import load_cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategies", nargs="+", choices=("bdi-only", "llm-only", "hybrid"), default=["bdi-only"])
    parser.add_argument("--cases", nargs="+", choices=[case["id"] for case in load_cases()])
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--runtime-dir", type=Path, default=Path(".tg/bin"))
    parser.add_argument("--output", type=Path, default=Path(".tg/campaigns"))
    args = parser.parse_args(argv)
    if args.repeat < 1 or len(set(args.strategies)) != len(args.strategies):
        parser.error("use positive repetitions and distinct strategies")
    args.runtime_dir = args.runtime_dir.resolve()
    if not all((args.runtime_dir / f"tg-{name}").is_file() for name in ("registry", "orchestrator", "messaging")):
        parser.error("prepare binaries with ./tg run studies/logistics/experiment.py or provide --runtime-dir")
    directory = args.output.resolve() / ("logistics-" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    manifest = {"study": "logistics", "created_at": datetime.now(timezone.utc).isoformat(),
                "strategies": args.strategies, "repetitions": args.repeat, "runs": []}
    cases = args.cases or [case["id"] for case in load_cases()]
    manifest["cases"] = cases
    manifest["status"] = "RUNNING"

    def save():
        (directory / "campaign.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def interrupt(*_):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    old = {key: os.environ.get(key) for key in ("LOGISTICS_CASE", "LOGISTICS_STRATEGY")}
    save()
    try:
        for repetition in range(1, args.repeat + 1):
            for case in cases:
                for strategy in args.strategies:
                    os.environ.update(LOGISTICS_CASE=case, LOGISTICS_STRATEGY=strategy)
                    run, summary = run_experiment(
                        Path(__file__).with_name("experiment.py"), output_root=directory / "runs",
                        runtime_dir=args.runtime_dir,
                    )
                    manifest["runs"].append({"directory": str(run.relative_to(directory)), "repetition": repetition,
                                             "case": case, "strategy": strategy, "status": summary["status"]})
                    save()
                    if summary["status"] == "CANCELLED":
                        raise KeyboardInterrupt
        manifest["status"] = "FAILED" if any(run["status"] != "COMPLETED" for run in manifest["runs"]) else "COMPLETED"
    except KeyboardInterrupt:
        manifest["status"] = "CANCELLED"
    except Exception as error:
        manifest.update(status="FAILED", error=str(error))
    finally:
        signal.signal(signal.SIGTERM, previous)
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        save()
    print(f"Campanha: {directory}\nEstado: {manifest['status']}")
    return {"COMPLETED": 0, "CANCELLED": 130}.get(manifest["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
