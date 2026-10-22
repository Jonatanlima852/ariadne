"""ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/greeting/scenario.py (usa o provedor configurado)."""
from ariadne_sdk import Scenario, Step
from studies.scenarios.greeting.agents.greeter import greeter

scenario = Scenario(
    agents=[greeter()],
    tasks=[Step("greet", "Dê boas-vindas à apresentação do Ariadne.")],
)
