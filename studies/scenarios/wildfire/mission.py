"""Missão wildfire: variáveis, agentes, declaração por caso/configuração e métricas do resultado.

Compartilhado pelo cenário declarativo (``scenario.py``), pela campanha
(``campaign.py``), pela análise (``analysis.py``), pelo laço em processo dos
testes (``loop.py``) e pelos testes. As métricas saem do ``MissionResult`` do
contrato (o JSON de ``mission-result.json``): estado final no contexto,
estado após cada rodada (``context_after``), resultados do planejador e
rastros BDI. Não há controlador de episódio em Python; o laço é o do
orquestrador Go.

| Variável | Padrão | Significado |
|---|---|---|
| ``WILDFIRE_CASE`` | ``three-fronts`` | caso (ver ``domain/cases.py``) |
| ``WILDFIRE_CONFIGURATION`` | ``ariadne`` | ``ariadne`` (comandante LLM + drones BDI) ou ``single-llm`` (piloto LLM) |
| ``WILDFIRE_DEMO`` | ``0`` | ``1`` usa os substitutos determinísticos, sem credencial |
| ``WILDFIRE_DRONES`` | do caso | sobrepõe o número de drones (varreduras) |
| ``WILDFIRE_DRONE_AGENTS`` | ``4`` | contêineres de drone BDI que servem os passos ``drone-*`` em rodízio |
| ``WILDFIRE_COMMAND_EVERY`` | ``1`` | cadência do comandante: ``1`` chama o modelo toda rodada |
"""
from dataclasses import dataclass
from datetime import datetime
import os

from ariadne_sdk import Mission, MissionLimits
from studies.scenarios.wildfire.agents.common import DEMO_PROVIDER
from studies.scenarios.wildfire.domain.adapters import (
    PLANNER_CAPABILITY, SINGLE_LLM_CAPABILITY, WORLD_STEP_ID, mission_context, mission_goal, restore_integers,
)
from studies.scenarios.wildfire.domain.cases import find_case
from studies.scenarios.wildfire.domain.world import chebyshev, initial_state, metrics, truth_at

CONFIGURATIONS = {'ariadne': PLANNER_CAPABILITY, 'single-llm': SINGLE_LLM_CAPABILITY}
LABELS = {'ariadne': 'Ariadne (comandante LLM + drones BDI)', 'single-llm': 'Piloto LLM'}
DRONE_AGENTS = 4
MAX_PARALLEL = 9  # um passo por drone; o validador aceita 10 passos e um é o mundo
RETRY_POLICY = {'max_attempts': 2, 'exclude_failed_agent': True}
# Passos paralelos se distribuem entre os drones BDI; FIRST_AVAILABLE mandaria todos ao primeiro.
SELECTION_POLICY = 'round_robin'
ALERT_RADIUS = 2  # distância (Chebyshev) para considerar que um drone "chegou" à estrutura do alerta


@dataclass(frozen=True)
class Settings:
    case_id: str = 'three-fronts'
    configuration: str = 'ariadne'
    demo: bool = False
    drones: int | None = None
    drone_agents: int = DRONE_AGENTS
    command_every: int = 1

    def __post_init__(self):
        if self.configuration not in CONFIGURATIONS:
            raise ValueError(f'unknown configuration: {self.configuration}; use {", ".join(CONFIGURATIONS)}')
        if int(self.drone_agents) < 1 or int(self.command_every) < 1 or (self.drones is not None and int(self.drones) < 1):
            raise ValueError('WILDFIRE_DRONES, WILDFIRE_DRONE_AGENTS and WILDFIRE_COMMAND_EVERY must be positive')
        find_case(self.case_id)

    @property
    def case(self):
        return find_case(self.case_id, drones=self.drones)

    @property
    def label(self):
        return f'wildfire-{self.case_id}-{self.configuration}'

    @property
    def execution_kind(self):
        return 'deterministic-integration-demo' if self.demo else 'real-llm'

    def to_dict(self):
        case = self.case
        return {'study': 'wildfire', 'case': case['id'], 'suite': case['suite'], 'configuration': self.configuration,
                'drones': int(case['drones']), 'drone_agents': int(self.drone_agents),
                'command_every': int(self.command_every), 'execution_kind': self.execution_kind}


def settings_from_env(environ=None) -> Settings:
    env = os.environ if environ is None else environ
    drones = env.get('WILDFIRE_DRONES', '').strip()
    return Settings(case_id=env.get('WILDFIRE_CASE', 'three-fronts'),
                    configuration=env.get('WILDFIRE_CONFIGURATION', 'ariadne'),
                    demo=env.get('WILDFIRE_DEMO', '0') == '1',
                    drones=int(drones) if drones else None,
                    drone_agents=int(env.get('WILDFIRE_DRONE_AGENTS', DRONE_AGENTS) or DRONE_AGENTS),
                    command_every=int(env.get('WILDFIRE_COMMAND_EVERY', '1') or 1))


def limits(case):
    """Rodadas até o horizonte mais a rodada DONE, paralelismo igual ao número de drones."""
    return MissionLimits(max_rounds=int(case['horizon']) + 3, max_parallel=min(int(case['drones']), MAX_PARALLEL),
                         round_deadline_ms=180000, planner_deadline_ms=180000)


def mission_for(case, configuration):
    if configuration not in CONFIGURATIONS:
        raise ValueError(f'unknown configuration: {configuration}')
    return Mission(goal=mission_goal(case), context=mission_context(case), limits=limits(case),
                   planner_capability=CONFIGURATIONS[configuration], retry_policy=RETRY_POLICY,
                   selection_policy=SELECTION_POLICY,
                   metadata={'study': 'wildfire', 'case': case['id'], 'suite': case['suite'],
                             'configuration': configuration, 'drones': int(case['drones'])})


def agents_for(settings: Settings):
    """Comandante + K drones BDI + mundo, ou piloto + mundo. Importa os agentes aqui
    para que a análise e os testes do domínio não precisem de Pydantic."""
    from studies.scenarios.wildfire.agents.drone.main import make_agent as drone_agent
    from studies.scenarios.wildfire.agents.planner.main import make_agent as commander_agent
    from studies.scenarios.wildfire.agents.single_llm.main import make_agent as pilot_agent
    from studies.scenarios.wildfire.agents.world.main import make_agent as world_agent
    if settings.configuration == 'single-llm':
        return [pilot_agent(demo=settings.demo), world_agent()]
    return [commander_agent(demo=settings.demo, command_every=settings.command_every),
            *(drone_agent(name=f'drone-{index}') for index in range(1, int(settings.drone_agents) + 1)),
            world_agent()]


def presentation(settings: Settings):
    """Rótulos editoriais do Mission Viewer; não alteram eventos nem resultados."""
    case = settings.case
    agents = {'world': {'label': 'Mundo', 'role': 'determinístico: aplica as ações, espalha o fogo, dispara o rádio'}}
    if settings.configuration == 'single-llm':
        agents['pilot'] = {'label': 'Piloto LLM', 'role': 'LLM: decide a ação concreta de cada drone'}
        description = 'Um único LLM pilota todos os drones; o mundo determinístico aplica e espalha o fogo.'
    else:
        agents['commander'] = {'label': 'Comandante LLM', 'role': 'LLM: lê mapa e rádio, dá metas e crenças aos drones'}
        for index in range(1, int(settings.drone_agents) + 1):
            agents[f'drone-{index}'] = {'label': f'Drone BDI {index}', 'role': 'BDI: delibera a ação do drone com reserva de bateria'}
        description = 'Um comandante LLM dá metas; drones BDI deliberam em paralelo; o mundo aplica e espalha o fogo.'
    steps = {WORLD_STEP_ID: {'label': 'Avançar o mundo'}}
    for index in range(1, int(case['drones']) + 1):
        steps[f'drone-d{index}'] = {'label': f'Decidir d{index}'}
    return {'title': f"Incêndio: {case['title']}", 'description': description, 'agents': agents, 'steps': steps}


# --- métricas de uma missão --------------------------------------------------

def _seconds_between(start, end):
    if not start or not end:
        return None
    parse = lambda text: datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    return round((parse(end) - parse(start)).total_seconds(), 4)


def _usage_total(usages, key):
    if not usages or any(key not in usage for usage in usages):
        return None
    return sum(int(usage[key]) for usage in usages)


def alert_cell(case):
    """Célula da primeira estrutura anunciada só pelo rádio, e o tique do anúncio."""
    for event in case.get('events') or []:
        hidden = (event.get('effects') or {}).get('hidden_structures') or {}
        if hidden:
            return next(iter(hidden)), int(event['tick'])
    return None, None


def round_states(document, case):
    """Estado inicial e estado após cada rodada PLAN, em ordem."""
    states = [initial_state(case)]
    for item in document.get('rounds') or []:
        if item.get('action') != 'PLANNER_ACTION_PLAN':
            continue
        state = restore_integers((item.get('context_after') or {}).get('state') or {})
        if state:
            states.append(state)
    return states


def curve(document, case):
    """Uma linha por tique: cinzas, focos, drones perdidos e drones a até ALERT_RADIUS da estrutura do alerta."""
    cell, _ = alert_cell(case)
    rows = []
    for state in round_states(document, case):
        near = 0
        if cell:
            near = sum(1 for d in state['drones'].values()
                       if d.get('condition') == 'ok' and chebyshev(d['at'], cell) <= ALERT_RADIUS)
        rows.append({'tick': int(state['tick']), 'burned': len(state['ash']), 'burning': len(state['fires']),
                     'intensity_total': sum(int(v) for v in state['fires'].values()),
                     'drones_lost': sum(1 for d in state['drones'].values() if d.get('condition') == 'lost'),
                     'near_alert': near})
    return rows


def episode_metrics(document, *, case, configuration, demo):
    """Uma observação lida só do ``MissionResult``.

    ``llm_calls`` conta as rodadas em que o planejador chamou um modelo real
    (``provider == "openai"``); atalhos sem modelo (sem fogo, horizonte,
    ordens permanentes) e o modo de demonstração não contam. Tokens vêm de
    ``planner_result.metadata.usage`` e ficam ``null`` quando alguma rodada
    real não os informa.
    """
    context = restore_integers(document.get('context') or {})
    state = context.get('state')
    rounds = document.get('rounds') or []
    planner_results = [item.get('planner_result') or {} for item in rounds]
    providers = [(result.get('metadata') or {}).get('provider') for result in planner_results]
    shortcuts = [(result.get('metadata') or {}).get('shortcut') for result in planner_results]
    real = [result for result in planner_results if (result.get('metadata') or {}).get('provider') == 'openai']
    usage = [result['metadata']['usage'] for result in real if 'usage' in (result.get('metadata') or {})]
    latencies = [float(result['metadata']['latency_ms']) for result in real if (result.get('metadata') or {}).get('latency_ms')]
    steps = [step for item in rounds for step in (item.get('result') or {}).get('step_results', [])]
    bdi_cycles, drone_plans = 0, {}
    for step in steps:
        trace = ((step.get('result') or {}).get('metadata') or {}).get('bdi_trace')
        if trace:
            bdi_cycles += int(trace.get('cycle_count') or 0)
            plan = ((step.get('result') or {}).get('metadata') or {}).get('selected_plan')
            drone_plans[plan] = drone_plans.get(plan, 0) + 1
    parallel = [sum(1 for step in (item.get('result') or {}).get('step_results', []) if step.get('step_id') != WORLD_STEP_ID)
                for item in rounds if item.get('action') == 'PLANNER_ACTION_PLAN']
    reassignments = sum(1 for step in steps if int((step.get('task') or {}).get('attempt') or 0) > 1)
    status = document.get('status')
    error = document.get('error')
    if isinstance(error, dict):
        error = error.get('message')
    measured = metrics(state, case) if state else None
    series = curve(document, case) if state else []
    cell, alert_tick = alert_cell(case)
    reaction = None
    if cell and alert_tick is not None:
        after = [row for row in series if row['tick'] > alert_tick and row['near_alert'] > 0]
        reaction = after[0]['tick'] - alert_tick if after else None
    hidden = (measured or {}).get('structures', {})
    row = {'case': case['id'], 'suite': case.get('suite'), 'configuration': configuration, 'drones': int(case['drones']),
           'execution_kind': 'deterministic-integration-demo' if demo else 'real-llm',
           'ticks': int(state['tick']) if state else 0, 'horizon': int(case['horizon']),
           'burned': measured['burned'] if measured else None,
           'cells': int(case['width']) * int(case['height']),
           'fires_remaining': measured['burning'] if measured else None,
           'extinguished': measured['extinguished'] if measured else None,
           'drops': measured['drops'] if measured else None,
           'structures_total': measured['structures_total'] if measured else None,
           'structures_burned': measured['structures_burned'] if measured else None,
           'alert_structure_status': hidden.get(cell, {}).get('condition') if cell else None,
           'alert_reaction_ticks': reaction,
           'drones_lost': measured['drones_lost'] if measured else None,
           'drones_offline': measured['drones_offline'] if measured else None,
           'accepted_actions': measured['accepted'] if measured else None,
           'rejected_actions': measured['rejected'] if measured else None,
           'idle_actions': measured['idle'] if measured else None,
           'wall_seconds': _seconds_between(document.get('created_at'), document.get('completed_at')),
           'rounds': len(rounds), 'planner_calls': len(rounds), 'llm_calls': len(real),
           'model_calls': sum(1 for p in providers if p in ('openai', DEMO_PROVIDER)),
           'standing_orders_rounds': sum(1 for s in shortcuts if s == 'standing_orders'),
           'planner_latency_mean_s': round(sum(latencies) / len(latencies) / 1000, 2) if latencies else None,
           'planner_latency_max_s': round(max(latencies) / 1000, 2) if latencies else None,
           'input_tokens': _usage_total(usage, 'input_tokens') if real else None,
           'output_tokens': _usage_total(usage, 'output_tokens') if real else None,
           'bdi_cycles': bdi_cycles, 'drone_plans': drone_plans,
           'max_parallel_steps': max(parallel, default=0), 'reassignments': reassignments,
           'mission_status': status, 'mission_id': document.get('mission_id'), 'curve': series,
           'result': ('error' if status not in ('MISSION_STATUS_COMPLETED', 'MISSION_STATUS_FAILED') and not state
                      else 'contained' if measured and measured['burning'] == 0 else 'partial'),
           'error': error if status != 'MISSION_STATUS_COMPLETED' else None}
    return row


def check_mission(document, settings: Settings):
    """Confere o ``mission-result.json``: estado, rodadas, passos e desfecho."""
    if document.get('status') != 'MISSION_STATUS_COMPLETED':
        raise AssertionError(f"mission did not complete: {document.get('error') or document.get('status')}")
    rounds = document.get('rounds') or []
    if not rounds or rounds[-1].get('action') != 'PLANNER_ACTION_DONE':
        raise AssertionError(f'expected the last round to be DONE, got {[item.get("action") for item in rounds]}')
    case = settings.case
    for item in rounds[:-1]:
        if item.get('action') != 'PLANNER_ACTION_PLAN':
            raise AssertionError(f"round {item.get('round')} is {item.get('action')}")
        steps = {step['step_id']: step for step in (item.get('result') or {}).get('step_results', [])}
        if WORLD_STEP_ID not in steps or steps[WORLD_STEP_ID].get('status') != 'WORKFLOW_STEP_STATUS_COMPLETED':
            raise AssertionError(f"round {item.get('round')}: world step missing or not completed")
        drone_steps = [sid for sid in steps if sid != WORLD_STEP_ID]
        if settings.configuration == 'single-llm' and drone_steps:
            raise AssertionError('single-llm rounds must not contain drone steps')
        if settings.configuration == 'ariadne' and not drone_steps:
            raise AssertionError(f"round {item.get('round')}: ariadne round without drone steps")
    state = restore_integers((document.get('context') or {}).get('state') or {})
    if not state:
        raise AssertionError('final context has no state')
    if state['fires'] and int(state['tick']) < int(case['horizon']):
        raise AssertionError('mission ended with fires left before the horizon')
    if int(state['tick']) != len(rounds) - 1:
        raise AssertionError(f"tick {state['tick']} does not match {len(rounds) - 1} PLAN rounds")
    return document
