"""Executor determinístico: o "mundo" da missão.

Recebe o estado autoritativo, a referência do caso e as propostas dos
entregadores (por binding) ou do Single LLM (inline). Aplica cada sequência
pelas transições da v2, na ordem decidida pelo planejador: ações inválidas
são rejeitadas e registradas; incidentes disparam antes da próxima ação e
interrompem a rodada. A saída volta ao contexto da missão pelo laço do
orquestrador, e é assim que o planejador vê o novo estado e os incidentes.
"""
from ariadne_sdk import Agent
from studies.scenarios.logistics.v2.domain.world import execute
from studies.scenarios.logistics.v3.domain.adapters import (
    EXECUTE_CAPABILITY, all_delivered, metrics, pending_orders, restore_integers,
)
from studies.scenarios.logistics.v3.domain.cases import incidents_for


def ordered_proposals(payload):
    proposals = payload.get('proposals') or {}
    sequence = [sid for sid in payload.get('order_sequence') or [] if sid in proposals]
    sequence += sorted(sid for sid in proposals if sid not in sequence)
    return [(sid, proposals[sid]) for sid in sequence]


def execute_round(task):
    payload = restore_integers(dict(task.payload))
    state = payload.get('state')
    if not isinstance(state, dict) or 'orders' not in state:
        raise ValueError('execute step requires payload.state from the mission context')
    schedule = incidents_for(payload.get('case'))
    applied, fired, stop_reason, last_rejection = [], [], '', ''
    for step_id, proposal in ordered_proposals(payload):
        entry = {'step_id': step_id, 'order': proposal.get('order', ''), 'vehicle': proposal.get('vehicle')}
        actions = proposal.get('actions') or []
        if not proposal.get('feasible', bool(actions)) or not actions:
            applied.append({**entry, 'status': 'skipped', 'accepted': 0, 'rejected': 0,
                            'reason': proposal.get('reason') or 'no actions proposed'})
            continue
        before_accepted, before_history = state['accepted_actions'], len(state['history'])
        outcome = execute(state, actions, schedule)
        state = outcome['state']
        rejected = sum(1 for item in state['history'][before_history:] if item.get('accepted') is False)
        delivered = [oid for oid in (proposal.get('order'),) if oid in state['deliveries']]
        status = 'incident' if outcome['incidents'] else 'rejected' if rejected else 'applied'
        applied.append({**entry, 'status': status, 'accepted': state['accepted_actions'] - before_accepted,
                        'rejected': rejected, 'reason': outcome['reason'], 'delivered': bool(delivered),
                        'proposed': len(actions)})
        if rejected:
            last_rejection = outcome['reason']
        if outcome['incidents']:
            fired, stop_reason = outcome['incidents'], outcome['reason']
            break
    feedback = {'reason': stop_reason or last_rejection, 'incidents': fired}
    return {'state': state, 'applied': applied, 'incidents': fired, 'feedback': feedback,
            'metrics': metrics(state), 'pending_orders': pending_orders(state),
            'all_delivered': all_delivered(state)}


def make_agent(**options):
    configuration = dict(name='execute', capabilities=[EXECUTE_CAPABILITY], handler=execute_round)
    return Agent(**(configuration | options))
