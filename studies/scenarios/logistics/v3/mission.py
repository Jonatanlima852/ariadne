"""Missão logística v3: declaração por caso/configuração e métricas do resultado.

Compartilhado pelo cenário declarativo (``scenario.py``), pelo coletor
(``benchmarks/run.py``) e pelos testes. As métricas saem do ``MissionResult``
do contrato (o JSON de ``mission-result.json``): estado final no contexto,
rodadas, resultados do planejador e rastros BDI. Não há controlador de
episódio em Python; o laço é o do orquestrador Go.
"""
from datetime import datetime

from ariadne_sdk import Mission, MissionLimits
from studies.scenarios.logistics.v3.domain.adapters import (
    EXECUTE_STEP_ID, PLANNER_CAPABILITY, SINGLE_LLM_CAPABILITY, metrics, mission_context, mission_goal,
    restore_integers,
)

CONFIGURATIONS = {'ariadne-v3': PLANNER_CAPABILITY, 'single-llm-v3': SINGLE_LLM_CAPABILITY}
DELIVERY_AGENTS = 3
MAX_ROUNDS = 20
RETRY_POLICY = {'max_attempts': 2, 'exclude_failed_agent': True}
# Passos paralelos se distribuem entre os entregadores; FIRST_AVAILABLE mandaria todos ao primeiro.
SELECTION_POLICY = 'round_robin'
DEMO_PROVIDER = 'deterministic-integration-substitute'


def limits(max_rounds=MAX_ROUNDS, delivery_agents=DELIVERY_AGENTS):
    """Rodadas, paralelismo igual ao número de entregadores e prazos folgados."""
    return MissionLimits(max_rounds=max_rounds, max_parallel=delivery_agents,
                         round_deadline_ms=180000, planner_deadline_ms=120000)


def mission_for(case, configuration, *, max_rounds=MAX_ROUNDS, delivery_agents=DELIVERY_AGENTS):
    if configuration not in CONFIGURATIONS:
        raise ValueError(f'unknown configuration: {configuration}')
    return Mission(goal=mission_goal(case), context=mission_context(case),
                   limits=limits(max_rounds, delivery_agents), planner_capability=CONFIGURATIONS[configuration],
                   retry_policy=RETRY_POLICY, selection_policy=SELECTION_POLICY,
                   metadata={'study': 'logistics-v3', 'case': case['id'], 'suite': case.get('suite', 'basic'),
                             'configuration': configuration})


def _seconds_between(start, end):
    if not start or not end:
        return None
    parse = lambda text: datetime.fromisoformat(text.replace('Z', '+00:00'))
    return round((parse(end) - parse(start)).total_seconds(), 4)


def _usage_total(usages, key):
    if not usages or any(key not in usage for usage in usages):
        return None
    return sum(int(usage[key]) for usage in usages)


def episode_metrics(document, *, case, configuration, demo):
    """Uma observação no espírito da v2, lida só do ``MissionResult``.

    ``llm_calls`` conta as rodadas em que o planejador chamou um modelo real
    (``provider == "openai"``); atalhos sem modelo (tudo entregue, nada
    viável) e o modo de demonstração não contam. Tokens vêm de
    ``planner_result.metadata.usage`` e ficam ``null`` quando alguma rodada
    real não os informa, como na v2.
    """
    context = restore_integers(document.get('context') or {})
    state = context.get('state')
    measured = metrics(state) if state else {'delivered': 0, 'total_orders': len(case['orders']), 'on_time': 0,
                                             'rejected_actions': 0, 'distance': 0, 'energy_consumed': 0,
                                             'simulation_minutes': 0, 'accepted_actions': 0}
    rounds = document.get('rounds') or []
    planner_results = [item.get('planner_result') or {} for item in rounds]
    real = [result for result in planner_results if (result.get('metadata') or {}).get('provider') == 'openai']
    usage = [result['metadata']['usage'] for result in real if 'usage' in (result.get('metadata') or {})]
    steps = [step for item in rounds for step in (item.get('result') or {}).get('step_results', [])]
    bdi_steps = []
    for item in rounds:
        for step in (item.get('result') or {}).get('step_results', []):
            trace = ((step.get('result') or {}).get('metadata') or {}).get('bdi_trace')
            if trace:
                bdi_steps.append({'round': item.get('round'), 'step_id': step.get('step_id'),
                                  'agent_id': (step.get('result') or {}).get('agent_id'),
                                  'cycles': int(trace.get('cycle_count') or 0),
                                  'final_status': trace.get('final_status'),
                                  'selected_plan': (step.get('result') or {}).get('metadata', {}).get('selected_plan')})
    parallel = [sum(1 for step in (item.get('result') or {}).get('step_results', []) if step.get('step_id') != EXECUTE_STEP_ID)
                for item in rounds if item.get('action') == 'PLANNER_ACTION_PLAN']
    reassignments = sum(1 for step in steps if int((step.get('task') or {}).get('attempt') or 0) > 1)
    status = document.get('status')
    output = document.get('output') or {}
    error = document.get('error')
    if isinstance(error, dict):
        error = error.get('message')
    complete = measured['delivered'] == measured['total_orders']
    return {'case': case['id'], 'suite': case.get('suite', 'basic'), 'configuration': configuration,
            'execution_kind': 'deterministic-integration-demo' if demo else 'real-llm',
            **measured,
            'wall_seconds': _seconds_between(document.get('created_at'), document.get('completed_at')),
            'rounds': len(rounds), 'planner_calls': len(rounds), 'llm_calls': len(real),
            'input_tokens': _usage_total(usage, 'input_tokens') if real else None,
            'output_tokens': _usage_total(usage, 'output_tokens') if real else None,
            'bdi_cycles': sum(step['cycles'] for step in bdi_steps), 'bdi_steps': bdi_steps,
            'parallel_steps_per_round': parallel,
            'max_parallel_steps': max(parallel, default=0), 'reassignments': reassignments,
            'mission_status': status, 'mission_id': document.get('mission_id'),
            'result': 'error' if status not in ('MISSION_STATUS_COMPLETED', 'MISSION_STATUS_FAILED') and not state
                      else 'complete' if complete else 'partial',
            'stop_reason': output.get('summary') or error or status, 'error': error if status != 'MISSION_STATUS_COMPLETED' else None}
