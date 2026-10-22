"""Carga reportada controlada para comparar políticas do runtime."""
import os
import time
from ariadne_sdk import Agent


def worker(name, load, delay_ms=30, **options):
    def respond(task):
        time.sleep(delay_ms / 1000)
        return {"text": task.goal}
    return Agent(name=name, capabilities=["benchmark-policy"], reported_load=load,
                 handler=respond, **options)


if __name__ == "__main__":
    agent = worker(os.getenv("AGENT_ID", "policy-a"), float(os.getenv("REPORTED_LOAD", "0")),
                   int(os.getenv("DELAY_MS", "30")))
    Agent.from_env(capabilities=agent.capabilities, reported_load=agent.reported_load,
                   handler=agent.handle).run()
