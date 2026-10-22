from ariadne_sdk import BdiAgent, Input, Plan

calendars = {"alice": [(9, 11), (14, 15)], "bob": [(10, 12), (16, 18)],
             "carol": [(9, 10), (13, 17)]}


def available(calendars, meeting, hour):
    end = hour + meeting["duration"]
    return end <= 18 and all(
        person in calendars and all(hour >= stop or end <= start for start, stop in calendars[person])
        for person in meeting["participants"]
    )


def scheduler():
    return BdiAgent(
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
    )
