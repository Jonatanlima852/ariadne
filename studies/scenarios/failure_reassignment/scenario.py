"""./ariadne run studies/scenarios/failure_reassignment/scenario.py — timeout e reassignment no runtime Go."""
from ariadne_sdk import Scenario, Step
from studies.agents.text import echo_agent

scenario = Scenario(
    agents=[
        echo_agent(name="a-slow", delay_seconds=0.5),
        echo_agent(name="b-healthy"),
    ],
    tasks=[Step(
        capability="echo", goal="Conclua com o agente disponível",
        deadline_ms=100, max_attempts=2, exclude_failed_agent=True,
    )],
)
