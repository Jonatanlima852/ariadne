"""Single LLM da v2 embrulhado como planejador de missão (linha de base).

Mesmo prompt, mesmas regras e mesmo contrato de ações da v2. A única
diferença é o transporte: em vez de um controlador Python aplicar as ações,
cada rodada vira um PLAN com um único passo ``execute``, cujo payload leva as
ações decididas; o executor determinístico as aplica e o laço devolve o novo
estado e o feedback ao modelo. Ações vazias viram DONE, como na v2.
"""
import json
import threading

from ariadne_sdk import LlmAgent, PlannerRequest, PlannerResponse, Prompt, TaskResult
from ariadne_sdk.llm import LlmCapability
from studies.scenarios.logistics.v2.agents.single_llm.main import INSTRUCTION
from studies.scenarios.logistics.v2.domain.models import Proposal, action_mapper
from studies.scenarios.logistics.v2.domain.world import RULES
from studies.scenarios.logistics.v3.agents.common import DemoClient, demo_enabled, llm_runtime, mark_demo
from studies.scenarios.logistics.v3.domain.adapters import (
    EXECUTE_STEP_ID, SINGLE_LLM_CAPABILITY, all_delivered, execute_step, metrics, pending_orders, restore_integers,
)

PROPOSAL_ID = 'single-llm'


def llm_view(request):
    """Exatamente o payload que o SingleLLM da v2 recebia do controlador."""
    state = restore_integers(request.context['state'])
    max_rounds = int(request.limits.get('max_rounds') or 0)
    return {'state': state, 'requests': request.context.get('requests', []),
            'feedback': request.context.get('feedback', {}), 'round': request.round,
            'remaining_rounds': max(max_rounds - request.round, 0)}


def build_response(request, proposal):
    state = restore_integers(request.context['state'])
    mapped = action_mapper(proposal)
    if not mapped['actions']:
        summary = mapped['explanation'] or 'no further actions proposed'
        return PlannerResponse.done({'metrics': metrics(state), 'delivered': sorted(state['deliveries']),
                                     'pending': pending_orders(state), 'summary': summary}, summary=summary).to_output()
    step = execute_step(state, request.context['case'], proposals={
        PROPOSAL_ID: {'feasible': True, 'order': '*', 'actions': mapped['actions'], 'explanation': mapped['explanation']}})
    return PlannerResponse.make_plan([step], final_step_id=EXECUTE_STEP_ID,
                                     workflow_id=f'single-llm-v3-round-{request.round}',
                                     summary=mapped['explanation'][:300]).to_output()


class SingleLlmPlanner(LlmAgent):
    runtime_name = 'logistics-v3-llm'

    def __init__(self, demo=None, **options):
        self.demo = demo_enabled(demo)
        self._local = threading.local()
        options.setdefault('name', 'single-llm')
        options.setdefault('runtime', llm_runtime(self.demo))
        if self.demo:
            options.setdefault('openai_client', DemoClient())
        elif options.get('openai_client') is None:
            from openai import OpenAI
            options['openai_client'] = OpenAI(max_retries=0, timeout=90)
        super().__init__(handlers=[LlmCapability(SINGLE_LLM_CAPABILITY, self._prompt, Proposal, self._mapper)],
                         **options)

    def _prompt(self, goal, payload):
        return Prompt(system=f'ROLE=SingleLLM\n{INSTRUCTION}\n{RULES}',
                      user=json.dumps(llm_view(self._local.request), ensure_ascii=False))

    def _mapper(self, proposal):
        return build_response(self._local.request, proposal)

    def handle(self, task):
        try:
            request = PlannerRequest.from_payload(task.payload)
        except ValueError as error:
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_FAILED',
                              trace=task.trace, error_code='ERROR_CODE_INVALID_TASK', error_message=str(error))
        state = restore_integers(request.context.get('state') or {})
        if state and all_delivered(state):
            response = PlannerResponse.done({'metrics': metrics(state), 'delivered': sorted(state['deliveries']),
                                             'pending': [], 'summary': 'all orders delivered'},
                                            summary='all orders delivered')
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_COMPLETED',
                              trace=task.trace, output=response.to_output(),
                              metadata={'provider': 'none', 'shortcut': 'all_delivered', 'model': self.model})
        self._local.request = request
        result = super().handle(task)
        return mark_demo(result) if self.demo else result


def make_agent(**options):
    return SingleLlmPlanner(**options)
