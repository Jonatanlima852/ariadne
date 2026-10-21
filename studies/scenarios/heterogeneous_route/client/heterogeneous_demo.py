"""Cenário ponta a ponta: uma pergunta, workflow LLM -> BDI -> LLM."""

import json
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../../sdk/python/src"),
)

from ariadne_sdk import RuntimeClient


GOAL = "Planeje uma rota de A para D e explique por que ela foi escolhida"


def main():
    address = os.getenv("ORCHESTRATOR_ADDR", "localhost:50052")
    with RuntimeClient(
        "heterogeneous-route",
        address,
        entry_capability="task-decomposition",
    ) as scenario:
        result = scenario.ask(GOAL).assert_completed()
        result.assert_agent_kind_used("llm").assert_agent_kind_used("bdi")

        route = result.steps["route"]["result"]
        assert route.metadata["selected_plan"] == "via_intermediate"
        assert route.output["route"] == ["A", "B", "D"]
        assert route.output["distance"] == 25

        default_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            "../runtime_metrics/results/heterogeneous-report.json",
        ))
        report_path = os.getenv("SCENARIO_REPORT_PATH", default_path)
        result.save(report_path)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        print(
            f"\nCENÁRIO APROVADO trace_id={result.trace_id} "
            f"run_id={result.run_id} report={report_path}"
        )


if __name__ == "__main__":
    main()
