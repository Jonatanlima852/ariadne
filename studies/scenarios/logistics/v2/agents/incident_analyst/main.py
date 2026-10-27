"""IncidentAnalyst: independently registered LLM agent."""
from studies.scenarios.logistics.v2.domain.models import Analysis
from studies.scenarios.logistics.v2.agents.common import llm, serve

INSTRUCTION = 'Analyze actual incident or execution feedback against current cargo, vehicles, map and pending orders. Identify affected_orders and which specialties must review (inventory, resource, route, energy). Explain recovery or alternative sources; never assert delivery.'


def make_agent(**options):
    return llm('IncidentAnalyst', Analysis, instructions=INSTRUCTION, **options)


if __name__ == '__main__':
    serve(make_agent)
