import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

from ariadne_sdk import BdiAgent

from beliefs import CALENDARS
from plans import PLAN_LIBRARY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [meeting-scheduler] %(message)s",
)
log = logging.getLogger(__name__)


class MeetingSchedulerAgent(BdiAgent):
    """Agente BDI que tenta marcar uma reunião: o desejo é "encontrar um
    horário, dentro do expediente, em que os participantes possam se
    reunir, o mais perto possível do horário preferido". Diferente do
    agente de rotas, aqui nem sempre existe uma solução perfeita — o
    agente precisa avaliar compromissos (quórum parcial, desvio de
    horário) e justificar a escolha."""

    default_agent_id = "meeting-scheduler-01"
    default_port = 60055
    runtime_name = "python-sdk-bdi"
    capabilities = ["meeting-scheduling"]
    beliefs = CALENDARS

    def desire(self, task):
        """Lê participantes, duração e horário preferido de task.payload.

        Campos esperados:
          participants         → lista de strings (nomes/IDs)
          duration_hours       → número (duração da reunião em horas)
          preferred_start_hour → número (horário preferido de início)
        """
        participants = task.payload.get("participants")
        duration = task.payload.get("duration_hours")
        preferred = task.payload.get("preferred_start_hour")

        if participants is None or duration is None or preferred is None:
            return None

        return {
            "participants": list(participants),
            "duration_hours": int(duration),
            "preferred_start_hour": int(preferred),
        }

    def handle(self, task):
        log.info("task received task_id=%s goal=%s", task.task_id, task.goal)
        result = super().handle(task)
        log.info("task finished task_id=%s status=%s", task.task_id, result.status)
        return result


def main():
    agent_id = os.getenv("AGENT_ID", "meeting-scheduler-01")
    agent = MeetingSchedulerAgent.from_env(
        name=f"Meeting Scheduler Agent ({agent_id})",
        capabilities=[os.getenv("CAPABILITY", "meeting-scheduling")],
        plan_library=PLAN_LIBRARY,
    )
    agent.run()


if __name__ == "__main__":
    main()
