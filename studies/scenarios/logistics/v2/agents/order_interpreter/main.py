"""OrderInterpreter: independently registered LLM agent."""
from studies.scenarios.logistics.v2.domain.models import Requirements
from studies.scenarios.logistics.v2.agents.common import llm, serve

INSTRUCTION = 'Extract every natural-language order literally. Do not invent or weaken requirements. Return structured orders with items as sku/quantity. Priority: larger number is more urgent.'


def make_agent(**options):
    return llm('OrderInterpreter', Requirements, instructions=INSTRUCTION, **options)


if __name__ == '__main__':
    serve(make_agent)
