"""Transport and LLM setup only; each role declares its own agent and prompt."""
import json
import os


def llm(role, schema, *, instructions, model=None, demo=None, mapper=None, **options):
    from openai import OpenAI
    from ariadne_sdk import LlmAgent, LlmCapability, Prompt
    from studies.scenarios.logistics.v2.domain.world import RULES
    if demo is None:
        demo = os.getenv('LOGISTICS_V2_DEMO', '0') == '1'
    model = model or os.getenv('LLM_MODEL', 'gpt-5.6-luna')
    if demo:
        from studies.scenarios.logistics.v2.demonstrations.substitutes import DemoClient, DemoLlmAgent
        cls, client = DemoLlmAgent, DemoClient()
    else:
        cls, client = LlmAgent, OpenAI(max_retries=0, timeout=90)
    prompt = lambda goal, context: Prompt(
        system=f'ROLE={role}\n{instructions}\n{RULES}',
        user=json.dumps(context, ensure_ascii=False))
    configuration = dict(name=role, model=model, openai_client=client,
        runtime='logistics-v2-demo' if demo else 'logistics-v2-llm',
        handlers=[LlmCapability('logistics-v2-' + role, prompt, schema, mapper)])
    return cls(**(configuration | options))


def serve(factory):
    factory(host=os.getenv('AGENT_HOST', 'localhost'),
            port=int(os.getenv('AGENT_PORT', '60051')),
            registry_addr=os.getenv('REGISTRY_ADDR', 'localhost:50051')).run()
