"""./ariadne run examples/echo.py"""
from ariadne_sdk import Agent, Scenario, Step

scenario = Scenario(
    agents=[Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})],
    tasks=[Step(capability="echo", goal="Olá, Ariadne!")],
)
