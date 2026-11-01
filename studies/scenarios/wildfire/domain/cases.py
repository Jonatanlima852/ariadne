"""Casos do cenário wildfire: grade, bases, drones, focos, obstáculos e eventos.

Cada caso é um dicionário completo e determinístico; os drones nascem nas
bases, em rodízio. ``events`` é a agenda oculta: o planejador nunca a recebe
em forma estruturada; o executor dispara o rádio no tique certo e recompõe,
pelo próprio caso, os fatos que só o rádio anunciou (``truth_at``).

Suítes: ``basic`` (sem eventos), ``alert`` (um alerta de rádio que muda a
missão) e ``stress`` (grade maior, mais focos, vento que dobra e drones que
saem do ar). ``all`` reúne as três.
"""
from copy import deepcopy

SUITES = ('basic', 'alert', 'stress')

CASES = [
    {
        'id': 'single-fire', 'suite': 'basic', 'title': 'Um foco, dois drones',
        'width': 12, 'height': 12, 'horizon': 10, 'wind': {'toward': 'E', 'speed': 1},
        'bases': {'B1': '1,1'}, 'drones': 2, 'fires': {'6,6': 1}, 'obstacles': [], 'structures': {},
        'briefing': 'Central: um foco de incêndio detectado em (6,6), vento fraco para LESTE. '
                    'Base B1 em (1,1). Apagar o foco antes que se espalhe.',
        'events': [],
    },
    {
        'id': 'three-fronts', 'suite': 'basic', 'title': 'Três frentes e uma escola a favor do vento',
        'width': 16, 'height': 16, 'horizon': 16, 'wind': {'toward': 'S', 'speed': 1},
        'bases': {'B1': '2,2', 'B2': '13,13'}, 'drones': 4,
        'fires': {'4,9': 1, '10,3': 2, '12,11': 1}, 'obstacles': [], 'structures': {'4,13': 'escola'},
        'briefing': 'Central: três focos ativos em (4,9), (10,3) e (12,11); vento para SUL. '
                    'Escola em (4,13) a favor do vento do foco oeste. Bases B1 (2,2) e B2 (13,13).',
        'events': [],
    },
    {
        'id': 'windy', 'suite': 'basic', 'title': 'Vento forte e linha de torres',
        'width': 16, 'height': 16, 'horizon': 16, 'wind': {'toward': 'E', 'speed': 2},
        'bases': {'B1': '4,7', 'B2': '11,7'}, 'drones': 4,
        'fires': {'3,3': 1, '3,12': 1, '8,8': 2, '11,4': 1},
        'obstacles': ['7,2', '7,3', '7,4', '7,5', '7,6'], 'structures': {'14,12': 'posto de saúde'},
        'briefing': 'Central: quatro focos com vento FORTE para LESTE (velocidade 2). Linha de torres de '
                    'transmissão de (7,2) a (7,6): zona de exclusão aérea. Posto de saúde em (14,12). '
                    'Bases B1 (4,7) e B2 (11,7).',
        'events': [],
    },
    {
        'id': 'hospital-alert', 'suite': 'alert', 'title': 'Alerta de rádio: hospital, base perdida e vento novo',
        'width': 16, 'height': 16, 'horizon': 18, 'wind': {'toward': 'N', 'speed': 1},
        'bases': {'B1': '8,1', 'B2': '8,14'}, 'drones': 6,
        'fires': {'9,3': 1, '3,4': 1, '6,11': 2, '13,12': 1, '2,13': 1, '12,7': 1},
        'obstacles': [], 'structures': {},
        'briefing': 'Central: seis focos ativos; vento para NORTE. Bases B1 (8,1, norte) e B2 (8,14, sul). '
                    'Nenhuma estrutura crítica conhecida até o momento.',
        'events': [
            {'tick': 5,
             'radio': 'URGENTE (Defesa Civil): hospital de campanha montado em (12,3) com 40 pacientes, '
                      'cercado por fumaça; prioridade máxima de proteção. A base NORTE B1 sofreu '
                      'curto-circuito e está FORA DE SERVIÇO: não pousar nem reabastecer lá, usar a base '
                      'SUL B2. Boletim meteorológico: o vento virou para LESTE.',
             'effects': {'hidden_structures': {'12,3': 'hospital de campanha'}, 'disable_bases': ['B1'],
                         'wind': {'toward': 'E', 'speed': 1}}},
        ],
    },
    {
        'id': 'storm', 'suite': 'stress', 'title': 'Tempestade: dez focos, vento que dobra, drones fora do ar',
        'width': 20, 'height': 20, 'horizon': 20, 'wind': {'toward': 'S', 'speed': 1},
        'bases': {'B1': '3,3', 'B2': '16,16', 'B3': '16,3'}, 'drones': 8,
        'fires': {'5,8': 1, '8,5': 2, '12,4': 1, '15,9': 1, '9,12': 2, '4,15': 1, '11,16': 1,
                  '18,12': 1, '7,18': 1, '13,13': 1},
        'obstacles': ['10,0', '10,1', '10,2', '10,3'], 'structures': {'14,6': 'escola'},
        'briefing': 'Central: dez focos ativos em toda a grade; vento para SUL. Torres de transmissão de '
                    '(10,0) a (10,3): zona de exclusão aérea. Escola em (14,6). Bases B1 (3,3), '
                    'B2 (16,16) e B3 (16,3).',
        'events': [
            {'tick': 4,
             'radio': 'URGENTE (Defesa Civil): hospital de campanha em (6,13) cercado por fumaça; '
                      'proteger com prioridade máxima. A base B1 (3,3) explodiu após curto-circuito e '
                      'está FORA DE SERVIÇO; reabastecer apenas em B2 ou B3.',
             'effects': {'hidden_structures': {'6,13': 'hospital de campanha'}, 'disable_bases': ['B1']}},
            {'tick': 8,
             'radio': 'Boletim meteorológico: rajadas de 60 km/h, o vento para SUL dobrou de velocidade.',
             'effects': {'wind': {'toward': 'S', 'speed': 2}}},
            {'tick': 12,
             'radio': 'Central: perda de enlace de rádio com os drones d3 e d6; estão fora do ar.',
             'effects': {'offline_drones': ['d3', 'd6']}},
        ],
    },
]


def load_cases(suite='all', ids=None):
    if suite != 'all' and suite not in SUITES:
        raise ValueError(f'unknown suite: {suite}; use {", ".join(SUITES)} or all')
    cases = [deepcopy(case) for case in CASES if suite == 'all' or case['suite'] == suite]
    if ids:
        unknown = set(ids) - {case['id'] for case in cases}
        if unknown:
            raise ValueError(f'unknown cases: {sorted(unknown)}')
        cases = [case for case in cases if case['id'] in ids]
    return cases


def find_case(case_id, *, drones=None):
    """Um caso por id; ``drones`` sobrepõe o número de drones (varreduras)."""
    for case in CASES:
        if case['id'] == case_id:
            found = deepcopy(case)
            if drones:
                found['drones'] = int(drones)
            return found
    raise ValueError(f'unknown case: {case_id}; use ' + ', '.join(c['id'] for c in CASES))


def case_reference(case):
    return {'id': case['id'], 'drones': int(case['drones'])}


def case_from_reference(reference):
    """O executor recebe só ``{"id", "drones"}`` no payload e recompõe o caso."""
    if not isinstance(reference, dict) or 'id' not in reference:
        raise ValueError('world step requires a case reference {"id", "drones"}')
    return find_case(reference['id'], drones=reference.get('drones'))
