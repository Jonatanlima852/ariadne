"""./ariadne run studies/scenarios/sequential_workflow/scenario.py — a referência ao output encadeia as etapas."""
from ariadne_sdk import Scenario, Step
from studies.scenarios.sequential_workflow.agents.text import echo_agent, uppercase_agent

echo = echo_agent()
uppercase = uppercase_agent()

first = Step(capability="echo", goal="Olá, agentes!", name="first")
second = Step(
    capability="uppercase", goal="Transforme o texto em maiúsculas", name="second",
    payload={"text": first.output["text"]},
)

scenario = Scenario(agents=[echo, uppercase], tasks=[first, second])
