"""./ariadne run examples/meeting.py — agendas, desejo e planos em um arquivo.

Propõe um horário; não escreve em calendários externos.
"""
from ariadne_sdk import BdiAgent, Input, Plan, Scenario, Step

calendars = {"alice": [(9, 11), (14, 15)], "bob": [(10, 12), (16, 18)],
             "carol": [(9, 10), (13, 17)]}


def available(calendars, meeting, hour):
    end = hour + meeting["duration"]
    return end <= 18 and all(
        person in calendars and all(hour >= stop or end <= start for start, stop in calendars[person])
        for person in meeting["participants"]
    )


scenario = Scenario(
    agents=[BdiAgent(
        name="scheduler", capabilities=["meeting"],
        beliefs=calendars, desire=Input("meeting"),
        plans=[Plan(
            f"start_{hour}",
            when=lambda beliefs, desire, hour=hour: available(beliefs, desire, hour),
            cost=lambda beliefs, desire, hour=hour: abs(hour - desire["preferred"]),
            execute=lambda beliefs, desire, hour=hour: {
                "start": hour, "end": hour + desire["duration"], "attendees": desire["participants"]},
        ) for hour in range(9, 18)] + [
            Plan("unavailable", execute=lambda beliefs, desire: {"start": None, "attendees": []}),
        ],
    )],
    tasks=[Step("meeting", "Encontre um horário comum próximo das 13h", payload={
        "meeting": {"participants": ["alice", "bob", "carol"], "duration": 1, "preferred": 13},
    })],
)
