"""Adaptadores dos clientes Docker históricos, preservados para compatibilidade."""

def run_llm(scenario, case, world):
    return scenario.submit(
        f"llm-{case['id']}",
        goal=case["request"],
        capabilities=["logistics-plan"],
        task_type="LOGISTICS_LLM_ONLY",
        payload={"world": world},
    )


def run_hybrid(scenario, case, world):
    return scenario.submit_workflow(
        case["request"],
        workflow_id=f"logistics-{case['id']}",
        final_step_id="execute",
        task_type="LOGISTICS_HYBRID",
        steps=[
            {
                "step_id": "interpret",
                "type": "INTERPRET_LOGISTICS_MISSION",
                "goal": case["request"],
                "required_capabilities": ["logistics-interpret"],
            },
            {
                "step_id": "execute",
                "type": "EXECUTE_LOGISTICS_MISSION",
                "goal": "Planeje e valide deterministicamente a missão estruturada.",
                "payload": {"world": world},
                "required_capabilities": ["logistics-execution"],
                "depends_on": ["interpret"],
                "input_bindings": [{
                    "source_step_id": "interpret",
                    "source_path": "output.mission",
                    "target_field": "mission",
                }],
            },
        ],
    )
