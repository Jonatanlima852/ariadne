"""./ariadne run studies/scenarios/basic_task/scenario.py"""
from ariadne_sdk import Scenario, Step
from studies.scenarios.basic_task.agents.echo import echo_agent

scenario = Scenario(
    agents=[echo_agent()],
    tasks=[Step(capability="echo", goal="Olá, Ariadne!")],
)
