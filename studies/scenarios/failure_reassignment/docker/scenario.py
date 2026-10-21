"""Benchmark determinístico de timeout e reassignment."""

import os
from pathlib import Path

from ariadne_sdk import RuntimeClient


ROOT = Path(__file__).resolve().parents[4]


def main():
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:52052")
    with RuntimeClient("failure-reassignment", address) as scenario:
        result = scenario.submit(
            "recover",
            goal="Complete após recuperar de um agente lento",
            capabilities=["recovery-test"],
            task_type="FAILURE_BENCHMARK",
            deadline_ms=100,
            max_attempts=2,
            exclude_failed_agent=True,
        )
        result.assert_completed()
        if result.agent_id != "b-healthy":
            raise AssertionError(
                f"expected reassignment to b-healthy, got {result.agent_id}"
            )

        report_path = Path(os.getenv(
            "SCENARIO_REPORT_PATH", ROOT / "studies/scenarios/failure_reassignment/runtime_metrics/results/failure-reassignment-report.json"
        ))
        scenario.report().assert_completed().save(report_path)
        print(
            f"CENÁRIO APROVADO agent_id={result.agent_id} "
            f"trace_id={scenario.trace_id} report={report_path}"
        )


if __name__ == "__main__":
    main()
