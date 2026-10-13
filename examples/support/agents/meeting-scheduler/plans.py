# Biblioteca de planos para o desejo "marcar uma reunião com certos
# participantes, duração e horário preferido". Cada plano recebe
# (desire, beliefs) e devolve um dict {"name", "reasoning_summary",
# "output", "cost"?} — formato esperado por tg_sdk.BdiAgent — ou None
# se não se aplica.
#
# Convenção de custo (menor = melhor): reuniões com todos presentes
# custam menos que reuniões parciais, e entre reuniões com todos
# presentes, vence a de menor desvio em relação ao horário preferido.
#   preferred_slot      -> custo 0          (o ideal)
#   earliest_full_slot  -> custo 1..N       (desvio + 1, nunca empata com 0)
#   partial_attendance  -> custo 10..       (peso forte em quem falta)
#   no_feasible_slot    -> sem custo (puro fallback)

from beliefs import WORKDAY_END, candidate_start_hours, free_participants


def preferred_slot_plan(desire, beliefs):
    participants = desire["participants"]
    duration = desire["duration_hours"]
    preferred = desire["preferred_start_hour"]
    end = preferred + duration

    if end > WORKDAY_END:
        return None

    free = free_participants(participants, preferred, end, beliefs)
    if len(free) != len(participants):
        return None

    return {
        "name": "preferred_slot",
        "cost": 0,
        "reasoning_summary": (
            f"horário preferido ({preferred}h-{end}h) está livre para "
            f"todos os {len(participants)} participantes; nenhum ajuste necessário."
        ),
        "output": {
            "start_hour": preferred,
            "end_hour": end,
            "attendees": free,
            "missing": [],
        },
    }


def earliest_full_slot_plan(desire, beliefs):
    participants = desire["participants"]
    duration = desire["duration_hours"]
    preferred = desire["preferred_start_hour"]

    for start in candidate_start_hours(duration):
        end = start + duration
        free = free_participants(participants, start, end, beliefs)
        if len(free) == len(participants):
            deviation = abs(start - preferred)
            return {
                "name": "earliest_full_slot",
                "cost": deviation + 1,
                "reasoning_summary": (
                    f"primeiro horário em que os {len(participants)} participantes "
                    f"estão todos livres é {start}h-{end}h "
                    f"(desvio de {deviation}h em relação ao horário preferido)."
                ),
                "output": {
                    "start_hour": start,
                    "end_hour": end,
                    "attendees": free,
                    "missing": [],
                },
            }
    return None


def partial_attendance_plan(desire, beliefs):
    participants = desire["participants"]
    duration = desire["duration_hours"]
    preferred = desire["preferred_start_hour"]
    quorum = len(participants) // 2 + 1

    best = None
    for start in candidate_start_hours(duration):
        end = start + duration
        free = free_participants(participants, start, end, beliefs)
        if len(free) < quorum or len(free) == len(participants):
            continue

        missing = [person for person in participants if person not in free]
        deviation = abs(start - preferred)
        cost = len(missing) * 10 + deviation
        if best is None or cost < best["cost"]:
            best = {
                "start": start, "end": end, "free": free,
                "missing": missing, "deviation": deviation, "cost": cost,
            }

    if best is None:
        return None

    return {
        "name": "partial_attendance",
        "cost": best["cost"],
        "reasoning_summary": (
            f"nenhum horário reúne todos; melhor compromisso encontrado é "
            f"{best['start']}h-{best['end']}h com {len(best['free'])}/{len(participants)} "
            f"participantes (faltam: {', '.join(best['missing'])}; "
            f"desvio de {best['deviation']}h em relação ao preferido)."
        ),
        "output": {
            "start_hour": best["start"],
            "end_hour": best["end"],
            "attendees": best["free"],
            "missing": best["missing"],
        },
    }


def no_feasible_slot_plan(desire, beliefs):
    participants = desire["participants"]
    return {
        "name": "no_feasible_slot",
        "reasoning_summary": (
            "nenhum horário do expediente reúne ao menos a maioria dos "
            "participantes; reunião não pôde ser agendada automaticamente."
        ),
        "output": {
            "start_hour": None,
            "end_hour": None,
            "attendees": [],
            "missing": participants,
        },
    }


PLAN_LIBRARY = [
    preferred_slot_plan,
    earliest_full_slot_plan,
    partial_attendance_plan,
    no_feasible_slot_plan,
]
