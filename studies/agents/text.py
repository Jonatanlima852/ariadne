"""Agentes de texto reutilizados nos estudos locais, sem serviços externos."""
import time
from ariadne_sdk import Agent


def echo_agent(name="echo", delay_seconds=0):
    def respond(task):
        if delay_seconds:
            time.sleep(delay_seconds)
        return {"text": task.goal}
    return Agent(name=name, capabilities=["echo"], handler=respond)


def uppercase_agent(name="uppercase"):
    return Agent(name=name, capabilities=["uppercase"],
                 handler=lambda task: {"text": task.payload["text"].upper()})
