"""Cliente da missão de rotas contra serviços já iniciados pelo Compose."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))

from ariadne_sdk import RuntimeClient
from studies.scenarios.routing.agents.planner_explainer.substitute import PROVIDER
from studies.scenarios.routing.mission import CONTEXT, GOAL, LIMITS, check_mission


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true",
                        help="exige que os agentes LLM usem o substituto determinístico (ROUTING_DEMO=1 no Compose)")
    args = parser.parse_args(argv)
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:50052")
    with RuntimeClient("heterogeneous-route", address) as client:
        result = client.run_mission(GOAL, context=CONTEXT, limits=LIMITS)

    document = check_mission(result.to_dict())
    providers = {step["result"].get("metadata", {}).get("provider")
                 for item in document["rounds"] for step in item.get("result", {}).get("step_results", [])
                 if step["result"].get("metadata", {}).get("provider")}
    expected = PROVIDER if args.demo else "openai"
    if providers != {expected}:
        raise AssertionError(f"LLM provider is {sorted(providers)}; expected {expected} (match --demo to ROUTING_DEMO)")

    default_path = ROOT / "studies/scenarios/routing/runtime_metrics/results/mission-result.json"
    report_path = os.getenv("SCENARIO_REPORT_PATH", str(default_path))
    result.save(report_path)
    print(json.dumps(document["output"], ensure_ascii=False, indent=2))
    print(f"\nCENÁRIO APROVADO mission_id={result.mission_id} rounds={len(result.rounds)} report={report_path}")


if __name__ == "__main__":
    main()
