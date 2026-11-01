"""Laço de missão em processo, para testes e calibração sem Docker.

Imita o que o orquestrador Go faz numa missão: chama o planejador com um
``PlannerRequest``, valida o plano, executa os passos ``drone-*`` (sem
dependências) e depois o passo ``world`` com os bindings, mescla a saída no
contexto (mescla rasa, como o Go) e repete até ``DONE``, ``ABORT`` ou o limite
de rodadas. O documento devolvido tem a forma do ``mission-result.json`` do
contrato, para que ``mission.episode_metrics`` e ``analysis`` leiam os dois.

Não é um modo de execução do estudo: não há contêineres, rede, prazos,
reatribuição nem eventos do runtime. As evidências do TG vêm de
``./ariadne run`` e ``./ariadne campaign``.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import uuid

from ariadne_sdk import PlannerResponse, Task, TaskResult
from ariadne_sdk.mission import validate_plan
from studies.scenarios.wildfire.domain.adapters import DRONE_CAPABILITY, WORLD_CAPABILITY
from studies.scenarios.wildfire.mission import CONFIGURATIONS, Settings, agents_for, mission_for

MAX_STEP_PAYLOAD_BYTES = 64 * 1024  # limite do validador do orquestrador


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _result_dict(result):
    document = {'task_id': result.task_id, 'agent_id': result.agent_id, 'status': result.status,
                'output': deepcopy(dict(result.output or {})), 'metadata': deepcopy(dict(result.metadata or {}))}
    if getattr(result, 'bdi', None):
        document['bdi'] = deepcopy(dict(result.bdi))
    if getattr(result, 'error_message', ''):
        document['error'] = {'code': getattr(result, 'error_code', ''), 'message': result.error_message}
    return document


def _handle(agent, task):
    """O mesmo caminho do servidor gRPC do SDK: dict vira TaskResult, exceção vira falha."""
    return TaskResult.from_proto(agent._execute_contract_task(task.to_proto()))


def _bind(payload, bindings, outputs):
    """Aplica ``input_bindings`` (``source_path`` = ``output``) em ``target_field`` com pontos."""
    payload = deepcopy(payload)
    for binding in bindings:
        value = outputs[binding['source_step_id']]
        target = payload
        parts = binding['target_field'].split('.')
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = deepcopy(value)
    return payload


class LocalLoop:
    def __init__(self, settings: Settings, agents=None):
        self.settings = settings
        self.agents = list(agents if agents is not None else agents_for(settings))
        capability = CONFIGURATIONS[settings.configuration]
        self.planner = next(agent for agent in self.agents if capability in agent.capabilities)
        self.drones = [agent for agent in self.agents if DRONE_CAPABILITY in agent.capabilities]
        self.world = next(agent for agent in self.agents if WORLD_CAPABILITY in agent.capabilities)
        self.mission = mission_for(settings.case, settings.configuration)
        self._drone_cursor = 0
        self.max_step_payload = 0

    def _capabilities(self):
        counts = {}
        for agent in self.agents:
            for capability in agent.capabilities:
                counts[capability] = counts.get(capability, 0) + 1
        return [{'capability_id': key, 'agent_count': value} for key, value in sorted(counts.items())]

    def _run_step(self, step, agent, round_number):
        payload = step['payload']
        encoded = len(json.dumps(payload, ensure_ascii=False))
        self.max_step_payload = max(self.max_step_payload, encoded)
        if encoded > MAX_STEP_PAYLOAD_BYTES:
            raise AssertionError(f"step {step['step_id']} payload has {encoded} bytes (limit {MAX_STEP_PAYLOAD_BYTES})")
        task = Task(task_id=f"r{round_number}-{step['step_id']}-{uuid.uuid4().hex[:6]}", goal=step['goal'],
                    type=step['type'], payload=payload, required_capabilities=tuple(step['required_capabilities']),
                    bdi={'goal': step['bdi_goal']} if step.get('bdi_goal') else {})
        result = _handle(agent, task)
        status = 'WORKFLOW_STEP_STATUS_COMPLETED' if result.status == 'TASK_STATUS_COMPLETED' else 'WORKFLOW_STEP_STATUS_FAILED'
        return {'step_id': step['step_id'], 'status': status, 'task': {'task_id': task.task_id, 'attempt': 1},
                'result': _result_dict(result)}

    def _next_drone(self):
        agent = self.drones[self._drone_cursor % len(self.drones)]
        self._drone_cursor += 1
        return agent

    def run(self):
        limits = self.mission.limits
        context = deepcopy(self.mission.context)
        history, rounds = [], []
        mission_id = 'local-' + uuid.uuid4().hex[:8]
        created = _now()
        status, output, error = 'MISSION_STATUS_FAILED', {}, {'message': f'mission exhausted max_rounds={limits.max_rounds} without DONE'}
        for number in range(1, int(limits.max_rounds) + 1):
            request = {'mission_id': mission_id, 'goal': self.mission.goal, 'round': number, 'context': deepcopy(context),
                       'history': deepcopy(history), 'available_capabilities': self._capabilities(),
                       'limits': limits.to_dict()}
            task = Task(task_id=f'plan-{number}', goal=self.mission.goal, type='MISSION_PLANNING', payload=request,
                        required_capabilities=(self.mission.planner_capability,))
            started = _now()
            planner_result = _handle(self.planner, task)
            record = {'round': number, 'planner_agent_id': self.planner.agent_id, 'started_at': started,
                      'planner_result': _result_dict(planner_result), 'planner_task': {'task_id': task.task_id, 'payload': request}}
            if planner_result.status != 'TASK_STATUS_COMPLETED':
                record.update(action='PLANNER_ACTION_UNKNOWN', planner_summary=planner_result.error_message, completed_at=_now())
                rounds.append(record)
                error = {'message': f'planner failed: {planner_result.error_message}'}
                break
            response = PlannerResponse.from_output(planner_result.output).validate()
            record['planner_summary'] = response.summary
            if response.action == 'DONE':
                context = {**context, **deepcopy(dict(response.context_update))}
                record.update(action='PLANNER_ACTION_DONE', context_after=deepcopy(context), completed_at=_now())
                rounds.append(record)
                status, output, error = 'MISSION_STATUS_COMPLETED', deepcopy(dict(response.output)), None
                break
            if response.action == 'ABORT':
                record.update(action='PLANNER_ACTION_ABORT', context_after=deepcopy(context), completed_at=_now())
                rounds.append(record)
                status, error = 'MISSION_STATUS_ABORTED', {'message': response.reason}
                break
            plan = validate_plan(response.plan)
            context = {**context, **deepcopy(dict(response.context_update))}
            outputs, step_results = {}, []
            pending = list(plan['steps'])
            while pending:
                ready = [step for step in pending if all(dep in outputs for dep in step['depends_on'])]
                if not ready:
                    raise AssertionError('plan has unsatisfiable dependencies')
                for step in ready:
                    pending.remove(step)
                    step = {**step, 'payload': _bind(step['payload'], step['input_bindings'], outputs)}
                    capability = step['required_capabilities'][0]
                    agent = self.world if capability == WORLD_CAPABILITY else self._next_drone()
                    executed = self._run_step(step, agent, number)
                    step_results.append(executed)
                    outputs[step['step_id']] = executed['result'].get('output', {})
            workflow_status = ('WORKFLOW_STATUS_COMPLETED' if all(s['status'].endswith('COMPLETED') for s in step_results)
                               else 'WORKFLOW_STATUS_FAILED')
            if workflow_status == 'WORKFLOW_STATUS_COMPLETED':
                context = {**context, **deepcopy(outputs[plan['final_step_id']])}
            history.append({'round': number, 'action': 'PLANNER_ACTION_PLAN', 'status': workflow_status,
                            'step_results': deepcopy(step_results), 'planner_summary': response.summary})
            record.update(action='PLANNER_ACTION_PLAN', plan=plan, result={'status': workflow_status, 'step_results': step_results},
                          context_after=deepcopy(context), completed_at=_now())
            rounds.append(record)
        document = {'mission_id': mission_id, 'status': status, 'output': output, 'context': context, 'rounds': rounds,
                    'created_at': created, 'completed_at': _now(),
                    'simulation': {'max_step_payload_bytes': self.max_step_payload, 'local_loop': True}}
        if error:
            document['error'] = error
        return document


def simulate(settings: Settings, agents=None):
    """Executa a missão em processo e devolve o documento no formato do contrato."""
    return LocalLoop(settings, agents).run()
