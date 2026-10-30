"""Transporte e modo de demonstração compartilhados pelos agentes da v3."""
import json
import os
from types import SimpleNamespace


def demo_enabled(value=None):
    if value is not None:
        return bool(value)
    return os.getenv('LOGISTICS_V3_DEMO', '0') == '1'


def llm_runtime(demo):
    return 'logistics-v3-demo' if demo else 'logistics-v3-llm'


class DemoClient:
    """Substituto determinístico do cliente OpenAI, só para integração.

    Decide pelo papel declarado na primeira linha do prompt de sistema
    (``ROLE=...``), como na v2: o plano cooperativo usa uma política fixa; a
    proposta do Single LLM reutiliza o substituto da v2. Nenhum dos dois mede
    capacidade de um modelo. (Não compara classes: um agente iniciado com
    ``python -m`` tem seu módulo como ``__main__``, e a mesma classe
    reimportada seria outro objeto.)
    """

    def __init__(self):
        self.responses = self

    def parse(self, *, model, input, text_format):
        role = input[0]['content'].splitlines()[0].split('=', 1)[1]
        context = json.loads(input[1]['content'])
        if role == 'CooperativePlanner':
            from studies.scenarios.logistics.v3.agents.planner.main import substitute_plan
            value = substitute_plan(context)
        else:
            from studies.scenarios.logistics.v2.demonstrations.substitutes import deterministic
            value = deterministic('SingleLLM', context)
        return SimpleNamespace(output_parsed=text_format.model_validate(value), usage=None)


def mark_demo(result):
    result.metadata.update(provider='deterministic-integration-substitute', model='no-real-model')
    return result
