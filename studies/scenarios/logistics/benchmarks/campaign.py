"""Coleta amostras brutas; a avaliação é executada em outro comando."""
import argparse
from pathlib import Path

from ariadne_sdk import Campaign
from ariadne_sdk.campaign import run_campaign
from studies.scenarios.logistics.datasets.loader import load_cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategies", nargs="+", choices=("llm-only", "hybrid"), default=["hybrid"])
    parser.add_argument("--cases", nargs="+", choices=[case["id"] for case in load_cases()])
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path(".ariadne/campaigns"))
    args = parser.parse_args(argv)
    if args.repeat < 1 or len(set(args.strategies)) != len(args.strategies):
        parser.error("use positive repetitions and distinct strategies")
    campaign = Campaign(
        Path(__file__).resolve().parents[1] / "scenario.py",
        matrix={"LOGISTICS_CASE": args.cases or [case["id"] for case in load_cases()],
                "LOGISTICS_STRATEGY": args.strategies},
        repeat=args.repeat, name="logistics", metadata={"study": "logistics"},
    )
    _, manifest = run_campaign(campaign, output_root=args.output)
    return {"COMPLETED": 0, "CANCELLED": 130}.get(manifest["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
