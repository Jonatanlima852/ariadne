"""Benchmark do cenário contra seu runtime Docker."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))
from tools.benchmarking import measured, task_case, summarize, workflow_sample, run_benchmark


def collect(client, address):
    from ariadne_sdk import RuntimeClient
    from studies.scenarios.routing.scenario import GOAL
    with RuntimeClient("benchmark-c", address, entry_capability="task-decomposition") as planner:
        workflow, latency = measured(lambda: planner.ask(GOAL))
    workflow.assert_completed().assert_agent_kind_used("bdi").assert_agent_kind_used("llm")
    sample = workflow_sample(workflow, latency)
    return {"C": [sample]}, [summarize(
        "C-heterogeneous", [sample], subtask_count=len(workflow.steps),
        explanation_present=bool(workflow.output.get("explanation")),
    )]


if __name__ == "__main__":
    run_benchmark(__file__, collect)
