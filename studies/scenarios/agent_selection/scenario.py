"""Seleção entre três agentes aptos; AGENT_SELECTION_POLICY escolhe a política estudada."""
import os
from ariadne_sdk import Scenario, Step
from studies.scenarios.agent_selection.agents.worker import worker

scenario = Scenario(
    agents=[worker("policy-a", 0.7), worker("policy-b", 0.1), worker("policy-c", 0.4)],
    tasks=[Step("benchmark-policy", f"Atenda a tarefa {index}",
                selection_policy=os.getenv("AGENT_SELECTION_POLICY", "ROUND_ROBIN")) for index in range(9)],
)
