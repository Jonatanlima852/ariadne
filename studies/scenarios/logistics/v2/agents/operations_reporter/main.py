"""OperationsReporter: independently registered LLM agent."""
from studies.scenarios.logistics.v2.domain.models import Report
from studies.scenarios.logistics.v2.agents.common import llm, serve

INSTRUCTION = 'Explain measured results, specialist decisions, revisions, unserved orders and failures in Portuguese. Treat measured metrics and deliveries as authoritative. Do not invent success or optimality.'


def make_agent(**options):
    return llm('OperationsReporter', Report, instructions=INSTRUCTION, **options)


if __name__ == '__main__':
    serve(make_agent)
