"""Demo standalone do MeetingSchedulerAgent — sem Registry nem Orchestrator.

Roda alguns cenários diretamente contra agent.execute_task e imprime,
passo a passo, as crenças relevantes, todos os planos avaliados (com
custo e raciocínio) e a decisão final. Serve para observar o
comportamento do agente com clareza, sem precisar subir o sistema todo.

Uso:
    python examples/support/agents/meeting-scheduler/demo.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../sdk/python/src"))
sys.path.insert(0, os.path.dirname(__file__))

from ariadne_sdk import Task

from beliefs import CALENDARS
from plans import PLAN_LIBRARY
from main import MeetingSchedulerAgent

SCENARIOS = [
    {
        "description": "Caso fácil: horário preferido já serve para todo mundo",
        "participants": ["alice", "dave"],
        "duration_hours": 1,
        "preferred_start_hour": 15,
    },
    {
        "description": "Preferido ocupado: precisa achar o primeiro horário com todos livres",
        "participants": ["alice", "bob", "carol"],
        "duration_hours": 1,
        "preferred_start_hour": 10,
    },
    {
        "description": "Sem horário comum: melhor compromisso é reunir a maioria",
        "participants": ["alice", "bob", "carol", "dave"],
        "duration_hours": 2,
        "preferred_start_hour": 9,
    },
    {
        "description": "Inviável: nem maioria consegue participar",
        "participants": ["alice", "bob", "carol"],
        "duration_hours": 4,
        "preferred_start_hour": 9,
    },
]


def make_task(scenario, task_id):
    return Task(
        task_id=task_id,
        goal="Marcar uma reunião",
        payload={
            "participants": scenario["participants"],
            "duration_hours": scenario["duration_hours"],
            "preferred_start_hour": scenario["preferred_start_hour"],
        },
        trace={"trace_id": f"trace-{task_id}"},
    )


def print_beliefs(participants):
    print("  crenças (agendas ocupadas no expediente 9h-18h):")
    for person in participants:
        busy = CALENDARS.get(person, [])
        busy_str = ", ".join(f"{s}h-{e}h" for s, e in busy) or "(livre o dia todo)"
        print(f"    {person}: {busy_str}")


def print_deliberation(agent, desire):
    print("  planos avaliados (em ordem de custo — vencedor é o de menor custo):")
    evaluated = []
    for plan_fn in agent.plan_library:
        plan = plan_fn(desire, agent.beliefs)
        evaluated.append((plan_fn.__name__, plan))

    # ordena para exibição: aplicáveis por custo (None por último), depois não aplicáveis
    def sort_key(item):
        _, plan = item
        if plan is None:
            return (2, 0)
        return (0, plan["cost"]) if "cost" in plan else (1, 0)

    for plan_name, plan in sorted(evaluated, key=sort_key):
        if plan is None:
            print(f"    [não aplicável] {plan_name}")
        else:
            cost = plan.get("cost", "—")
            print(f"    [aplicável, custo={cost}] {plan['name']}: {plan['reasoning_summary']}")


def print_result(result):
    metadata = dict(result.metadata)
    output = dict(result.output)
    print(f"  -> intenção escolhida: {metadata.get('selected_plan')}")
    print(f"     raciocínio: {metadata.get('reasoning_summary')}")
    print(f"     resultado: {output}")


def main():
    agent = MeetingSchedulerAgent(
        agent_id="meeting-scheduler-demo",
        name="Meeting Scheduler Agent (demo)",
        capabilities=["meeting-scheduling"],
        host="localhost",
        port=0,
        registry_addr="localhost:50051",
        beliefs=CALENDARS,
        plan_library=PLAN_LIBRARY,
    )

    for index, scenario in enumerate(SCENARIOS, start=1):
        task = make_task(scenario, task_id=f"demo-{index}")
        desire = agent.desire(task)

        print(f"\n=== Cenário {index}: {scenario['description']} ===")
        print(f"  desejo: reunir {desire['participants']} por {desire['duration_hours']}h, "
              f"preferencialmente às {desire['preferred_start_hour']}h")
        print_beliefs(desire["participants"])
        print_deliberation(agent, desire)

        result = agent.execute_task(task)
        print_result(result)


if __name__ == "__main__":
    main()
