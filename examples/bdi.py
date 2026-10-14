"""./ariadne run examples/bdi.py — só o plano escolhido é executado."""
from ariadne_sdk import BdiAgent, Plan, Scenario, Step

scenario = Scenario(
    agents=[BdiAgent(name="routes", capabilities=["route"], plans=[
        Plan("direct", cost=30, execute=lambda beliefs, desire: {"route": ["A", "D"]}),
        Plan("via_b", cost=25, execute=lambda beliefs, desire: {"route": ["A", "B", "D"]}),
    ])],
    tasks=[Step("route", "Ir de A para D")],
)
