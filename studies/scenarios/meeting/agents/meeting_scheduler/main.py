"""Agendador de reuniões: agente BDI deliberativo com agendas como crenças.

O objetivo é "encontrar um horário, dentro do expediente, em que os
participantes possam se reunir, o mais perto possível do horário
preferido". Nem sempre existe solução perfeita: os planos avaliam
compromissos (quórum parcial, desvio de horário) pelo custo.
"""
from ariadne_sdk import BdiAgent
from ariadne_sdk.plans import InputError

from studies.scenarios.meeting.agents.meeting_scheduler.beliefs import CALENDARS
from studies.scenarios.meeting.agents.meeting_scheduler.plans import GOAL, PLANS

FIELDS = ("participants", "duration_hours", "preferred_start_hour")


def desire(task):
    """Objetivo com parâmetros lidos de task.payload; campos faltantes invalidam a tarefa."""
    missing = [field for field in FIELDS if field not in task.payload]
    if missing:
        raise InputError("missing payload input: " + ", ".join(missing))
    return {
        "name": GOAL,
        "participants": list(task.payload["participants"]),
        "duration_hours": int(task.payload["duration_hours"]),
        "preferred_start_hour": int(task.payload["preferred_start_hour"]),
    }


def meeting_scheduler(**options):
    configuration = dict(
        agent_id="meeting-scheduler-01", name="Meeting Scheduler Agent", capabilities=["meeting-scheduling"],
        runtime="python-sdk-bdi", beliefs={"calendars": CALENDARS}, goal=desire, plans=PLANS,
    )
    return BdiAgent(**(configuration | options))
