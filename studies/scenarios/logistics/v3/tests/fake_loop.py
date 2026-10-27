"""Imitação em processo do laço de missão do orquestrador, só para testes.

Reproduz as regras da frente B que importam aos agentes: PlannerRequest com
contexto, histórico e capacidades; execução dos passos respeitando
``depends_on`` e ``input_bindings`` (``output`` -> ``proposals.<step>``);
mesclagem rasa de ``context_update`` e da saída do passo final no contexto.
Não substitui o teste de integração com os binários Go.
"""
import itertools

from collections.abc import Mapping

from ariadne_sdk import PlannerResponse, Task, TaskResult
from studies.scenarios.logistics.v3.domain.adapters import DELIVERY_CAPABILITY, EXECUTE_CAPABILITY

_ids = itertools.count(1)


def _task(step, payload, capability):
    return Task(task_id=f'fake-{next(_ids)}', goal=step['goal'], type=step['type'], payload=payload,
                required_capabilities=(capability,), bdi={'goal': step['bdi_goal']} if step.get('bdi_goal') else {})


def run_round(plan, agents):
    """Executa um plano com agentes locais; devolve step_results no formato do contrato."""
    results, outputs = [], {}
    for step in plan['steps']:
        if any(outputs.get(dep) is None for dep in step['depends_on']):
            results.append({'step_id': step['step_id'], 'status': 'WORKFLOW_STEP_STATUS_SKIPPED'})
            continue
        payload = dict(step['payload'])
        for binding in step['input_bindings']:
            target = payload
            parts = binding['target_field'].split('.')
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = outputs[binding['source_step_id']]
        capability = step['required_capabilities'][0]
        agent = agents[capability]
        task = _task(step, payload, capability)
        try:
            result = agent.handle(task)
        except Exception as error:  # Agent._execute_contract_task faria o mesmo
            result = TaskResult(task_id=task.task_id, agent_id=agent.agent_id, status='TASK_STATUS_FAILED',
                                error_code='ERROR_CODE_EXECUTION_FAILED', error_message=str(error))
        if isinstance(result, Mapping):
            result = TaskResult(task_id=task.task_id, agent_id=agent.agent_id, status='TASK_STATUS_COMPLETED', output=result)
        completed = result.status == 'TASK_STATUS_COMPLETED'
        outputs[step['step_id']] = dict(result.output) if completed else None
        results.append({'step_id': step['step_id'],
                        'status': 'WORKFLOW_STEP_STATUS_COMPLETED' if completed else 'WORKFLOW_STEP_STATUS_FAILED',
                        'task': {'task_id': 'fake', 'payload': payload, 'required_capabilities': [capability]},
                        'result': {'agent_id': result.agent_id, 'status': result.status,
                                   'output': outputs[step['step_id']] or {}, 'metadata': dict(result.metadata),
                                   **({'error': {'message': result.error_message}} if not completed else {})}})
    final = outputs.get(plan['final_step_id'])
    return results, final


def run_mission(planner, agents, goal, context, *, max_rounds=20, max_parallel=3, delivery_agents=3):
    """Devolve (status, context, rounds, planner_results)."""
    context = dict(context)
    history, rounds, planner_results = [], [], []
    capabilities = [{'capability_id': DELIVERY_CAPABILITY, 'agent_count': delivery_agents},
                    {'capability_id': EXECUTE_CAPABILITY, 'agent_count': 1}]
    for number in range(1, max_rounds + 1):
        request = {'mission_id': 'fake', 'goal': goal, 'round': number, 'context': context, 'history': history,
                   'available_capabilities': capabilities,
                   'limits': {'max_rounds': max_rounds, 'max_parallel': max_parallel}}
        result = planner.handle(Task(task_id=f'plan-{number}', goal=goal, type='MISSION_PLANNING',
                                     payload=request, required_capabilities=tuple(planner.capabilities)))
        planner_results.append(result)
        if result.status != 'TASK_STATUS_COMPLETED':
            return 'FAILED', context, rounds, planner_results
        response = PlannerResponse.from_output(result.output)
        context.update(response.context_update)
        if response.action == 'DONE':
            return 'COMPLETED', context, rounds, planner_results
        if response.action == 'ABORT':
            return 'ABORTED', context, rounds, planner_results
        step_results, final = run_round(response.plan, agents)
        status = 'WORKFLOW_STATUS_COMPLETED' if final is not None else 'WORKFLOW_STATUS_FAILED'
        if final is not None:
            context.update(final)
        history.append({'round': number, 'action': 'PLANNER_ACTION_PLAN', 'status': status,
                        'planner_summary': response.summary, 'step_results': step_results})
        rounds.append({'round': number, 'plan': response.plan, 'step_results': step_results, 'status': status})
    return 'FAILED', context, rounds, planner_results
