"""Benchmark do cenário contra seu runtime Docker."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sdk/python/src"))
from tools.benchmarking import measured, task_case, summarize, workflow_sample, run_benchmark


def collect(client, address):
    samples = task_case(client, "A-basic", "benchmark-basic", 10)
    return {"A": samples}, [summarize("A-basic", samples)]


if __name__ == "__main__":
    run_benchmark(__file__, collect)
