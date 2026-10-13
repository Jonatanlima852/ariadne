"""Coleta amostras brutas; a avaliação é executada em outro comando."""
import argparse
from pathlib import Path

from tg_sdk import Campaign
from tg_sdk.campaign import run_campaign
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
    campaign = Campaign(
        Path(__file__).with_name("experiment.py"),
        matrix={"LOGISTICS_CASE": args.cases or [case["id"] for case in load_cases()],
                "LOGISTICS_STRATEGY": args.strategies},
        repeat=args.repeat, name="logistics", metadata={"study": "logistics"},
    )
    _, manifest = run_campaign(campaign, output_root=args.output, runtime_dir=args.runtime_dir)
    return {"COMPLETED": 0, "CANCELLED": 130}.get(manifest["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
