from ariadne_sdk import Agent


def echo_agent():
    return Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})


def uppercase_agent():
    return Agent(name="uppercase", capabilities=["uppercase"],
                 handler=lambda task: {"text": task.payload["text"].upper()})
