"""Executor determinístico: o "mundo" da missão.

Recebe o estado autoritativo, a referência do caso e as ações dos drones (por
binding, uma por passo BDI, ou inline, a lista inteira do piloto). Aplica as
ações pelas regras de ``world.py``, rejeita as inválidas, avança o fogo um
tique e dispara os eventos agendados. A saída volta ao contexto da missão
pelo laço do orquestrador (mescla rasa: ``state`` é substituído inteiro).
Só o rádio dos eventos sai daqui; os efeitos de rádio ficam na verdade
oculta, recomputada do caso.
"""
from ariadne_sdk import Agent
from studies.scenarios.wildfire.domain.adapters import WORLD_CAPABILITY, restore_integers
from studies.scenarios.wildfire.domain.cases import case_from_reference
from studies.scenarios.wildfire.domain.world import step


def collect_actions(payload):
    """``payload.actions`` é ``{passo: saída}``: uma ação (BDI) ou ``{"actions": [...]}`` (piloto)."""
    outputs = payload.get('actions') or {}
    sequence = [sid for sid in payload.get('order_sequence') or [] if sid in outputs]
    sequence += sorted(sid for sid in outputs if sid not in sequence)
    actions = []
    for sid in sequence:
        output = outputs[sid]
        if not isinstance(output, dict):
            continue
        if isinstance(output.get('actions'), list):
            actions.extend(item for item in output['actions'] if isinstance(item, dict))
        elif output.get('action'):
            actions.append({'drone': output.get('drone'), 'action': output.get('action'),
                            'target': output.get('target'), 'plan': output.get('plan')})
    return actions


def world_round(task):
    payload = restore_integers(dict(task.payload))
    state = payload.get('state')
    if not isinstance(state, dict) or 'fires' not in state or 'drones' not in state:
        raise ValueError('world step requires payload.state from the mission context')
    case = case_from_reference(payload.get('case'))
    outcome = step(state, collect_actions(payload), case)
    fire = outcome['fire']
    return {'state': outcome['state'], 'tick': outcome['tick'], 'applied': outcome['applied'],
            'lost': outcome['lost'],
            'fire': {'ignited': len(fire['ignited']), 'ash': len(fire['ash']),
                     'structures_burned': fire['structures_burned']},
            'events': outcome['events'], 'metrics': outcome['metrics'],
            'fires_remaining': outcome['fires_remaining'], 'done': outcome['done']}


def make_agent(**options):
    configuration = dict(name='world', capabilities=[WORLD_CAPABILITY], handler=world_round)
    return Agent(**(configuration | options))
