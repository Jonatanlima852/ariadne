"""Carga reportada controlada para comparar políticas do runtime."""
import time
from ariadne_sdk import Agent


def worker(name, load, delay_ms=30, **options):
    def respond(task):
        time.sleep(delay_ms / 1000)
        return {"text": task.goal}
    return Agent(name=name, capabilities=["benchmark-policy"], reported_load=load,
                 handler=respond, **options)
