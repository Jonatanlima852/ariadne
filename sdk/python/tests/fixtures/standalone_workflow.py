"""Fixture autocontida para execução fora de qualquer pacote do repositório."""
from ariadne_sdk import Agent, Scenario, Step

echo = Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})
uppercase = Agent(
    name="uppercase", capabilities=["uppercase"],
    handler=lambda task: {"text": task.payload["text"].upper()},
)

first = Step(capability="echo", goal="Olá, agentes!", name="first")
second = Step(
    capability="uppercase", goal="Transforme o texto em maiúsculas", name="second",
    payload={"text": first.output["text"]},
)

scenario = Scenario(agents=[echo, uppercase], tasks=[first, second])
