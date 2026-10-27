"""MissionDecomposer: independently registered LLM agent."""
from studies.scenarios.logistics.v2.domain.models import Mission
from studies.scenarios.logistics.v2.agents.common import llm, serve

INSTRUCTION = 'Choose an order of service using priority (larger first), deadlines and current incident analysis. Include every outstanding order once. Describe tasks and dependencies for stock -> vehicle -> route -> energy -> validation -> execution. On incidents, prioritize affected orders if useful. Use dependency task names inventory, resource, route, energy, validation, execution, with requires listing predecessor task names. Return order_ids, dependencies and explanation.'


def make_agent(**options):
    return llm('MissionDecomposer', Mission, instructions=INSTRUCTION, **options)


if __name__ == '__main__':
    serve(make_agent)
