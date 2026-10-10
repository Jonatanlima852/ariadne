"""./tg run examples/bdi.py — classes especializadas usam o mesmo executor."""
from tg_sdk import BdiAgent, Scenario, Step, plan


class RouteAgent(BdiAgent):
    capabilities = ["route"]

    def desire(self, task):
        return task.goal

    @plan
    def direct(self, desire, beliefs):
        return {"cost": 30, "route": ["A", "D"]}

    @plan
    def via_b(self, desire, beliefs):
        return {"cost": 25, "route": ["A", "B", "D"]}


scenario = Scenario(
    agents=[RouteAgent()],
    tasks=[Step(capability="route", goal="Ir de A para D")],
)
