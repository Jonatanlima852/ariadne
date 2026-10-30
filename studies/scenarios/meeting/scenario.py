"""Propõe um horário de reunião; o agente BDI delibera entre planos por custo e não escreve em calendários externos."""
from ariadne_sdk import Scenario, Step
from studies.scenarios.meeting.agents.meeting_scheduler.main import meeting_scheduler

scenario = Scenario(
    agents=[meeting_scheduler()],
    tasks=[Step("meeting-scheduling", "Encontre um horário comum próximo das 13h", payload={
        "participants": ["alice", "bob", "carol"], "duration_hours": 1, "preferred_start_hour": 13,
    })],
)
