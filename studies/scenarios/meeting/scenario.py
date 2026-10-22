"""Propõe um horário; não escreve em calendários externos."""
from ariadne_sdk import Scenario, Step
from studies.scenarios.meeting.agents.scheduler import scheduler

scenario = Scenario(
    agents=[scheduler()],
    tasks=[Step("meeting", "Encontre um horário comum próximo das 13h", payload={
        "meeting": {"participants": ["alice", "bob", "carol"], "duration": 1, "preferred": 13},
    })],
)
