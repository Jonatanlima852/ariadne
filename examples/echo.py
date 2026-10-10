"""./tg run examples/echo.py"""
from tg_sdk import Agent, Scenario, Step

scenario = Scenario(
    agents=[Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})],
    tasks=[Step(capability="echo", goal="Olá, TG!")],
)
