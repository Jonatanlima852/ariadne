# Biblioteca de planos para o objetivo "schedule_meeting" (participantes,
# duração e horário preferido nos parâmetros do objetivo; agendas nas
# crenças). Cada proposta recebe (params, calendars) e devolve
# {"cost", "output"} ou None se não se aplica; goal_plan a transforma em um
# GoalPlan do SDK: o contexto é "há proposta", o custo é o da proposta e o
# corpo devolve a saída.
#
# Convenção de custo (menor = melhor): reuniões com todos presentes
# custam menos que reuniões parciais, e entre reuniões com todos
# presentes, vence a de menor desvio em relação ao horário preferido.
#   preferred_slot      -> custo 0          (o ideal)
#   earliest_full_slot  -> custo 1..N       (desvio + 1, nunca empata com 0)
#   partial_attendance  -> custo 10..       (peso forte em quem falta)
#   no_feasible_slot    -> sem custo (puro fallback)

from ariadne_sdk import GoalPlan

from .beliefs import WORKDAY_END, candidate_start_hours, free_participants

GOAL = "schedule_meeting"


def preferred_slot(params, calendars):
    participants, duration, preferred = params["participants"], params["duration_hours"], params["preferred_start_hour"]
    end = preferred + duration
    if end > WORKDAY_END:
        return None
    free = free_participants(participants, preferred, end, calendars)
    if len(free) != len(participants):
        return None
    return {"cost": 0, "output": {"start_hour": preferred, "end_hour": end, "attendees": free, "missing": []}}


def earliest_full_slot(params, calendars):
    participants, duration, preferred = params["participants"], params["duration_hours"], params["preferred_start_hour"]
    for start in candidate_start_hours(duration):
        end = start + duration
        free = free_participants(participants, start, end, calendars)
        if len(free) == len(participants):
            return {"cost": abs(start - preferred) + 1,
                    "output": {"start_hour": start, "end_hour": end, "attendees": free, "missing": []}}
    return None


def partial_attendance(params, calendars):
    participants, duration, preferred = params["participants"], params["duration_hours"], params["preferred_start_hour"]
    quorum = len(participants) // 2 + 1
    best = None
    for start in candidate_start_hours(duration):
        end = start + duration
        free = free_participants(participants, start, end, calendars)
        if len(free) < quorum or len(free) == len(participants):
            continue
        missing = [person for person in participants if person not in free]
        cost = len(missing) * 10 + abs(start - preferred)
        if best is None or cost < best["cost"]:
            best = {"cost": cost, "output": {"start_hour": start, "end_hour": end, "attendees": free, "missing": missing}}
    return best


def no_feasible_slot(params, calendars):
    return {"cost": None, "output": {"start_hour": None, "end_hour": None, "attendees": [],
                                     "missing": list(params["participants"])}}


def goal_plan(name, proposal, *, fallback=False):
    def candidate(beliefs, goal):
        return proposal(goal.params, beliefs["calendars"])
    return GoalPlan(
        name, goal=GOAL,
        context=lambda beliefs, goal: candidate(beliefs, goal) is not None,
        cost=None if fallback else (lambda beliefs, goal: candidate(beliefs, goal)["cost"]),
        body=lambda beliefs, goal: candidate(beliefs, goal)["output"],
    )


PLANS = [
    goal_plan("preferred_slot", preferred_slot),
    goal_plan("earliest_full_slot", earliest_full_slot),
    goal_plan("partial_attendance", partial_attendance),
    goal_plan("no_feasible_slot", no_feasible_slot, fallback=True),
]
