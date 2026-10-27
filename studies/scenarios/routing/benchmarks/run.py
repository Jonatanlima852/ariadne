"""Benchmark do cenário contra seu runtime Docker: uma missão de rotas."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))
from tools.benchmarking import measured, summarize, run_benchmark


def collect(client, address):
    from ariadne_sdk import RuntimeClient
    from studies.scenarios.routing.mission import CONTEXT, GOAL, LIMITS, check_mission
    with RuntimeClient("benchmark-c", address) as planner:
        mission, latency = measured(lambda: planner.run_mission(GOAL, context=CONTEXT, limits=LIMITS))
    check_mission(mission.to_dict())
    sample = {"latency_ms": latency, "agent_id": "", "status": mission.status, "mission": mission.to_dict()}
    return {"C": [sample]}, [summarize(
        "C-heterogeneous", [sample], rounds=len(mission.rounds),
        explanation_present=bool(mission.output.get("explanation")),
    )]


if __name__ == "__main__":
    run_benchmark(__file__, collect)
