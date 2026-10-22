# Base de crenças do agente: a agenda de cada participante, como uma
# lista de intervalos ocupados (start_hour, end_hour) num expediente
# fixo. Fixo neste exemplo, mas poderia vir de um serviço de calendário.

WORKDAY_START = 9
WORKDAY_END = 18

CALENDARS = {
    "alice": [(9, 11), (14, 15)],
    "bob": [(10, 12), (16, 18)],
    "carol": [(9, 10), (13, 17)],
    "dave": [(11, 13)],
}


def is_free(person, start, end, calendars=CALENDARS):
    """A pessoa está livre em [start, end) se nenhum compromisso se sobrepõe."""
    for busy_start, busy_end in calendars.get(person, []):
        if start < busy_end and end > busy_start:
            return False
    return True


def free_participants(participants, start, end, calendars=CALENDARS):
    """Lista, dentre os participantes, quem está livre em [start, end)."""
    return [person for person in participants if is_free(person, start, end, calendars)]


def candidate_start_hours(duration_hours):
    """Gera os horários de início possíveis dentro do expediente."""
    start = WORKDAY_START
    while start + duration_hours <= WORKDAY_END:
        yield start
        start += 1
