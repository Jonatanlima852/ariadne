from ariadne_sdk import Agent


def echo_agent():
    return Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})
