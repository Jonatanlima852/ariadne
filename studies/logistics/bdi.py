"""Planejamento simbólico do estudo logístico."""
from tg_sdk import BdiAgent, plan
from .domain import plan_mission


class LogisticsBdiAgent(BdiAgent):
    capabilities = ["logistics-execution"]
    default_agent_id = "bdi-agent-01"

    def desire(self, task):
        if task.payload.get("mission") and task.payload.get("world"):
            return {"kind": "logistics-mission", "mission": task.payload["mission"], "world": task.payload["world"]}
        return None

    @plan(name="safe_logistics_mission", priority=100)
    def safe_logistics_mission(self, desire, beliefs):
        if desire.get("kind") != "logistics-mission":
            return None
        result = plan_mission(desire["world"], desire["mission"])
        return {
            "cost": result["final_state"]["elapsed_minutes"] if result["feasible"] else 10**6,
            "reasoning_summary": (
                "plano validado por busca determinística e precondições do domínio"
                if result["feasible"]
                else "missão rejeitada porque nenhuma sequência satisfaz as restrições"
            ),
            **result,
        }
