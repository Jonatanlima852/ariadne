"""Piloto LLM: um único modelo decide a ação concreta de cada drone (linha de base).

Mesma vista do mapa e do rádio, mesmas regras e mesmo vocabulário de ações
do braço cooperativo. A diferença é o nível de decisão: aqui o modelo emite
``move``/``drop``/``resupply``/``hold`` com alvo para cada drone, e cada
rodada vira um PLAN com um único passo ``world`` cujo payload leva as ações.
Sem ações, o mundo avança do mesmo jeito (drones ociosos); só os atalhos
(sem fogo, horizonte) encerram a missão.
"""
import json
import threading
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ariadne_sdk import LlmAgent, PlannerRequest, PlannerResponse, Prompt, TaskResult
from ariadne_sdk.llm import LlmCapability
from studies.scenarios.wildfire.agents.common import DemoClient, demo_enabled, llm_runtime, mark_demo
from studies.scenarios.wildfire.agents.planner.main import done_response, shortcut
from studies.scenarios.wildfire.domain.adapters import (
    SINGLE_LLM_CAPABILITY, WORLD_STEP_ID, active_drones, planner_view, restore_integers, world_step,
)
from studies.scenarios.wildfire.domain.world import chebyshev, describe_rules, normalize_cell


class DroneAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    drone: str
    action: Literal['move', 'drop', 'resupply', 'hold']
    target: str | None = Field(description='Cell "x,y" for move (destination) or drop (burning cell); otherwise null')
    reason: str = Field(description='Short rationale')


class PilotDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['PLAN', 'DONE', 'ABORT']
    summary: str = Field(description='One sentence about the decision')
    reason: str = Field(description='Required for ABORT, otherwise empty')
    actions: list[DroneAction] = Field(description='For PLAN: exactly one action per active drone')


INSTRUCTION = (
    'You pilot every drone of a wildfire squadron directly. Each round, read the map (fires with intensity, '
    'ash, bases, drones with battery and water) and the radio, and output exactly ONE action per active drone: '
    'move (target = destination cell; the drone flies up to the speed limit toward it along a path that avoids '
    'obstacles), drop (target = a burning cell on the drone\'s own cell or adjacent to it, 8 neighbours), '
    'resupply (only on an ACTIVE base cell) or hold. Respect water and battery budgets and keep a battery '
    'reserve to reach a usable base: a drone that reaches 0 battery outside an active base is lost. The radio '
    'is the only source of some facts (a base out of service still shows as active in telemetry; a structure '
    'to protect may only be announced there). A deterministic world applies the actions, spreads the fire and '
    'reports accepted and rejected actions; a rejected action was wasted, so fix it next round. Spread drones '
    'across fronts, attack where the fire threatens structures and where it will spread (downwind), and do not '
    'idle drones with water. Answer DONE only when no fire is left or the horizon is reached; ABORT only if the '
    'data is inconsistent.'
)


def pilot_prompt(request):
    state = restore_integers(request.context.get('state') or {})
    return Prompt(system=f'ROLE=Pilot\n{INSTRUCTION}\n{describe_rules(state)}',
                  user=json.dumps(planner_view(request), ensure_ascii=False))


def normalize_actions(items):
    actions = []
    for item in items:
        target = item.get('target')
        if target not in (None, '', 'null'):
            try:
                target = normalize_cell(target)
            except ValueError:
                target = str(target)
        else:
            target = None
        actions.append({'drone': str(item.get('drone', '')), 'action': str(item.get('action', '')).lower(),
                        'target': target, 'reason': str(item.get('reason') or '')[:200]})
    return actions


def build_response(request, decision):
    if decision.action == 'ABORT':
        return PlannerResponse.abort(decision.reason or decision.summary, summary=decision.summary).to_output()
    decided = shortcut(request)
    if decision.action == 'DONE' and decided is not None:
        return decided[0].to_output()
    context = restore_integers(request.context)
    actions = normalize_actions([item.model_dump() for item in decision.actions])
    summary = decision.summary
    if decision.action == 'DONE':
        summary = 'model answered DONE with fires left; the world advances with idle drones'
    step = world_step(context['state'], context['case'], actions=actions)
    return PlannerResponse.make_plan([step], final_step_id=WORLD_STEP_ID,
                                     workflow_id=f'single-llm-round-{request.round}', summary=summary[:300],
                                     context_update={'last_plan': {'round': request.round, 'actions': actions,
                                                                   'summary': summary}}).to_output()


def substitute_pilot(view):
    """Política gulosa para a demonstração sem credenciais (não é um benchmark).

    Não lê o rádio: reabastece na base mais próxima segundo a telemetria,
    ataca o foco mais próximo e nunca gerencia reserva com cuidado. Serve só
    para integrar o caminho do piloto.
    """
    fires = [item['cell'] for item in view.get('fires', [])]
    bases = {b['at']: bid for bid, b in view.get('bases', {}).items()}
    rules = view.get('rules') or {}
    actions = []
    for drone_id, info in sorted(view.get('drones', {}).items()):
        if info.get('condition') != 'ok':
            continue
        at = info['at']
        if info['water'] <= 0 or info['battery'] <= 6:
            if at in bases:
                actions.append({'drone': drone_id, 'action': 'resupply', 'target': None, 'reason': 'demo: resupply'})
            else:
                base = min(bases, key=lambda c: (chebyshev(at, c), c))
                actions.append({'drone': drone_id, 'action': 'move', 'target': base, 'reason': 'demo: to base'})
            continue
        if at in bases and info['water'] < rules.get('water_capacity', 3):
            actions.append({'drone': drone_id, 'action': 'resupply', 'target': None, 'reason': 'demo: top up'})
            continue
        if not fires:
            actions.append({'drone': drone_id, 'action': 'hold', 'target': None, 'reason': 'demo: no fire'})
            continue
        fire = min(fires, key=lambda c: (chebyshev(at, c), c))
        if chebyshev(at, fire) <= 1:
            actions.append({'drone': drone_id, 'action': 'drop', 'target': fire, 'reason': 'demo: drop'})
        else:
            actions.append({'drone': drone_id, 'action': 'move', 'target': fire, 'reason': 'demo: approach'})
    return {'action': 'PLAN', 'summary': f'demo: {len(actions)} greedy action(s)', 'reason': '', 'actions': actions}


class Pilot(LlmAgent):
    runtime_name = 'wildfire-llm'

    def __init__(self, demo=None, **options):
        self.demo = demo_enabled(demo)
        self._local = threading.local()
        options.setdefault('name', 'pilot')
        options.setdefault('runtime', llm_runtime(self.demo))
        if self.demo:
            options.setdefault('openai_client', DemoClient())
        super().__init__(handlers=[LlmCapability(SINGLE_LLM_CAPABILITY, self._prompt, PilotDecision, self._mapper)],
                         **options)

    def _client(self):
        """Cliente OpenAI criado na primeira execução, não na declaração: validar o
        cenário (``./ariadne check``) não exige credencial. Sem retentativas do
        cliente: a política de retry é a do runtime."""
        with self._client_lock:
            if self._openai is None:
                from openai import OpenAI
                self._openai = OpenAI(max_retries=0, timeout=120)
            return self._openai

    def _prompt(self, goal, payload):
        return pilot_prompt(self._local.request)

    def _mapper(self, decision):
        return build_response(self._local.request, decision)

    def handle(self, task):
        try:
            request = PlannerRequest.from_payload(task.payload)
        except ValueError as error:
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_FAILED',
                              trace=task.trace, error_code='ERROR_CODE_INVALID_TASK', error_message=str(error))
        decided = shortcut(request)
        if decided is not None:
            response, why = decided
            return TaskResult(task_id=task.task_id, agent_id=self.agent_id, status='TASK_STATUS_COMPLETED',
                              trace=task.trace, output=response.to_output(),
                              metadata={'provider': 'none', 'shortcut': why, 'model': self.model})
        self._local.request = request
        result = super().handle(task)
        return mark_demo(result) if self.demo else result


def make_agent(**options):
    return Pilot(**options)
