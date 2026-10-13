"""Validação integrada do endpoint SubmitWorkflow síncrono."""

import os

from tg_sdk import RuntimeClient


def main():
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:53052")
    with RuntimeClient("workflow-sequential", address) as scenario:
        result = scenario.submit_workflow(
            "Execute duas tasks em sequência",
            workflow_id="sequential-echo",
            final_step_id="second",
            steps=[
                {
                    "step_id": "first",
                    "goal": "first",
                    "capabilities": ["echo"],
                },
                {
                    "step_id": "second",
                    "goal": "second",
                    "capabilities": ["echo"],
                    "depends_on": ["first"],
                },
            ],
        ).assert_completed()

        if list(result.steps) != ["first", "second"]:
            raise AssertionError(f"unexpected step order: {list(result.steps)}")
        if result.output.get("echo") != "second":
            raise AssertionError(f"unexpected final output: {result.output}")
        if report_path := os.getenv("SCENARIO_REPORT_PATH"):
            result.save(report_path)
        print(
            f"CENÁRIO APROVADO workflow_id={result.workflow_id} "
            f"run_id={result.run_id} trace_id={result.trace_id}"
        )


if __name__ == "__main__":
    main()
