"""./tg run examples/recovery.py — timeout e reassignment no runtime Go."""
import time
from tg_sdk import Agent, Scenario, Step


def slow(task):
    time.sleep(0.5)
    return {"text": task.goal}


scenario = Scenario(
    agents=[
        Agent(name="a-slow", capabilities=["echo"], handler=slow),
        Agent(name="b-healthy", capabilities=["echo"], handler=lambda task: {"text": task.goal}),
    ],
    tasks=[Step(
        capability="echo", goal="Conclua com o agente disponível",
        deadline_ms=100, max_attempts=2, exclude_failed_agent=True,
    )],
)
