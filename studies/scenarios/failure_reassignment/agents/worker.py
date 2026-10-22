"""Trabalhador com atraso controlado para observar nova atribuição."""
import os
import time
from ariadne_sdk import Agent


def echo_agent(name="echo", delay_seconds=0, **options):
    def respond(task):
        time.sleep(delay_seconds)
        return {"text": task.goal}
    return Agent(name=name, capabilities=["echo"], handler=respond, **options)


if __name__ == "__main__":
    agent = echo_agent(delay_seconds=float(os.getenv("DELAY_MS", "0")) / 1000)
    Agent.from_env(capabilities=[os.getenv("CAPABILITY", "recovery-test")], handler=agent.handle).run()
