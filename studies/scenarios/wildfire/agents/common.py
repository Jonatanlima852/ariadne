"""Transporte e modo de demonstração compartilhados pelos agentes LLM do wildfire."""
import json
import os
from types import SimpleNamespace

DEMO_PROVIDER = 'deterministic-integration-substitute'


def demo_enabled(value=None):
    if value is not None:
        return bool(value)
    return os.getenv('WILDFIRE_DEMO', '0') == '1'


def llm_runtime(demo):
    return 'wildfire-demo' if demo else 'wildfire-llm'


class DemoClient:
    """Substituto determinístico do cliente OpenAI, só para integração.

    Decide pelo papel declarado na primeira linha do prompt de sistema
    (``ROLE=...``): o comandante usa uma política fixa de ordens; o piloto, uma
    política gulosa de ações. Nenhum dos dois mede capacidade de um modelo.
    (Não compara classes: um agente iniciado com ``python -m`` tem seu módulo
    como ``__main__``, e a mesma classe reimportada seria outro objeto.)
    """

    def __init__(self):
        self.responses = self

    def parse(self, *, model, input, text_format):
        role = input[0]['content'].splitlines()[0].split('=', 1)[1]
        view = json.loads(input[1]['content'])
        if role == 'Commander':
            from studies.scenarios.wildfire.agents.planner.main import substitute_command
            value = substitute_command(view)
        elif role == 'Pilot':
            from studies.scenarios.wildfire.agents.single_llm.main import substitute_pilot
            value = substitute_pilot(view)
        else:
            raise ValueError(f'unknown demo role {role!r}')
        return SimpleNamespace(output_parsed=text_format.model_validate(value), usage=None)


def mark_demo(result):
    result.metadata.update(provider=DEMO_PROVIDER, model='no-real-model')
    return result
