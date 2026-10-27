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


def serve(factory):
    factory(host=os.getenv('AGENT_HOST', 'localhost'),
            port=int(os.getenv('AGENT_PORT', '60051')),
            registry_addr=os.getenv('REGISTRY_ADDR', 'localhost:50051')).run()


class DemoClient:
    """Substituto determinístico do cliente OpenAI, só para integração.

    Decide pelo esquema pedido (``text_format``): a proposta do Single LLM
    reutiliza o substituto da v2; o plano cooperativo usa uma política fixa.
    Nenhum dos dois mede capacidade de um modelo.
    """

    def __init__(self):
        self.responses = self

    def parse(self, *, model, input, text_format):
        context = json.loads(input[1]['content'])
        from studies.scenarios.logistics.v3.agents.planner.main import CooperativePlan, substitute_plan
        if text_format is CooperativePlan:
            value = substitute_plan(context)
        else:
            from studies.scenarios.logistics.v2.demonstrations.substitutes import deterministic
            value = deterministic('SingleLLM', context)
        return SimpleNamespace(output_parsed=text_format.model_validate(value), usage=None)


def mark_demo(result):
    result.metadata.update(provider='deterministic-integration-substitute', model='no-real-model')
    return result
