"""Benchmark do cenário contra seu runtime Docker."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))
from tools.benchmarking import measured, task_case, summarize, workflow_sample, run_benchmark


def collect(client, address):
    recovered, latency = measured(lambda: client.submit(
        "D-recovery", goal="recover", capabilities=["benchmark-recovery"],
        task_type="FAILURE_BENCHMARK", deadline_ms=100,
        max_attempts=2, exclude_failed_agent=True,
    ))
    recovered.assert_completed()
    if recovered.agent_id != "b-healthy":
        raise AssertionError(f"reassignment selected {recovered.agent_id}")
    sample = {"latency_ms": latency, "agent_id": recovered.agent_id, "status": recovered.status}
    return {"D": [sample]}, [summarize("D-reassignment", [sample], reassigned=True)]


if __name__ == "__main__":
    run_benchmark(__file__, collect)
