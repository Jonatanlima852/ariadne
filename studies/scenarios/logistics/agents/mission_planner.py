"""Declaração reutilizável; o SDK administra o ciclo do agente."""
from ariadne_sdk import BdiAgent, Input, Plan
from ..planning import plan_mission


def mission_planner(**options):
    configuration = dict(
        name="mission-planner", agent_id="mission-planner-01",
        capabilities=["logistics-execution"],
        beliefs=Input("world"), desire=Input("mission"),
        plans=[Plan("safe_logistics_mission", execute=plan_mission)],
    )
    return BdiAgent(**(configuration | options))
