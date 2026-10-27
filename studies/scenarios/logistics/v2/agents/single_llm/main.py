"""SingleLLM: independently registered LLM agent."""
from studies.scenarios.logistics.v2.domain.models import Proposal, action_mapper
from studies.scenarios.logistics.v2.agents.common import llm, serve

INSTRUCTION = 'You alone decide all logistics actions. Propose an executable action sequence for outstanding orders, respecting stock, vehicle capacity, energy, map, priority and deadlines. You may serve several orders. After feedback, revise from the NEW current state, never replay completed actions. Use origin/destination for MOVE. Empty actions means stop. You have no symbolic planner or repair service.'


def make_agent(**options):
    return llm('SingleLLM', Proposal, instructions=INSTRUCTION, mapper=action_mapper, **options)


if __name__ == '__main__':
    serve(make_agent)
