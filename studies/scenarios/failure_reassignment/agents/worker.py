"""Trabalhador com atraso controlado para observar nova atribuição."""
import time
from ariadne_sdk import Agent


def echo_agent(name="echo", delay_seconds=0, **options):
    def respond(task):
        time.sleep(delay_seconds)
        return {"text": task.goal}
    return Agent(name=name, capabilities=["echo"], handler=respond, **options)
