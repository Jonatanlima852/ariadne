"""Casos da v3: os mesmos arquivos JSON da v2, lidos no lugar, sem cópia.

A agenda de incidentes de cada caso fica fora do contexto da missão: só o
agente executor a consulta, por ``incidents_for``, a partir da referência
``{"id", "suite"}`` que viaja no payload do passo ``execute``.
"""
import json
from pathlib import Path

V2 = Path(__file__).resolve().parents[2] / 'v2'
DATASETS = V2 / 'datasets'
SUITES = {'basic': ['basic.json'], 'stress': ['stress.json'], 'all': ['basic.json', 'stress.json']}


def load_suite(suite='basic'):
    if suite not in SUITES:
        raise ValueError(f'unknown suite: {suite}')
    cases = []
    for name in SUITES[suite]:
        for case in json.loads((DATASETS / name).read_text(encoding='utf-8')):
            case.setdefault('suite', name.removesuffix('.json'))
            cases.append(case)
    return cases


def load_cases(suite='basic', ids=None):
    cases = load_suite(suite)
    if ids:
        unknown = set(ids) - {case['id'] for case in cases}
        if unknown:
            raise ValueError(f'unknown cases: {sorted(unknown)}')
        cases = [case for case in cases if case['id'] in ids]
    return cases


def find_case(case_id, suite=None):
    for case in load_suite(suite or 'all'):
        if case['id'] == case_id:
            return case
    raise ValueError(f'unknown case: {case_id}')


def case_reference(case):
    return {'id': case['id'], 'suite': case.get('suite', 'basic')}


def incidents_for(reference):
    """Agenda oculta de incidentes; o planejador nunca a recebe."""
    if not isinstance(reference, dict) or 'id' not in reference:
        raise ValueError('execute step requires a case reference {"id", "suite"}')
    return find_case(reference['id'], reference.get('suite'))['incidents']
