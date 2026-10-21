"""ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/llm_greeting/scenario.py (usa o provedor configurado)."""
from pydantic import BaseModel
from ariadne_sdk import LlmAgent, Prompt, Scenario, Step


class Greeting(BaseModel):
    text: str


scenario = Scenario(
    agents=[LlmAgent(name="greeter", capabilities=["greet"], output_schema=Greeting,
                    prompt=lambda goal, payload: Prompt("Responda brevemente em português.", goal))],
    tasks=[Step("greet", "Dê boas-vindas à apresentação do Ariadne.")],
)
