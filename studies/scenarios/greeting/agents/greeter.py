from pydantic import BaseModel
from ariadne_sdk import LlmAgent, Prompt


class Greeting(BaseModel):
    text: str


def greeter():
    return LlmAgent(name="greeter", capabilities=["greet"], output_schema=Greeting,
                    prompt=lambda goal, payload: Prompt("Responda brevemente em português.", goal))
