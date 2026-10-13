import os
from unittest import TestCase
from unittest.mock import patch
from pydantic import BaseModel
from tg_sdk import LlmAgent, LlmCapability, Prompt, Scenario, Task


class Answer(BaseModel):
    text: str


class DeclarationTests(TestCase):
    def test_scenario_has_no_client_or_execution_state(self):
        with patch('grpc.insecure_channel', side_effect=AssertionError('network')):
            scenario = Scenario()
        for attribute in ('_channel', '_stub', 'trace_id', 'submit', 'results'):
            self.assertFalse(hasattr(scenario, attribute), attribute)

    def test_llm_constructor_does_not_create_provider_client(self):
        with patch.dict(os.environ, {}, clear=True), patch('openai.OpenAI') as constructor:
            agent = LlmAgent(name='extract', capabilities=['extract'],
                             prompt=lambda goal, payload: Prompt('Extract.', goal), output_schema=Answer)
            constructor.assert_not_called()
            client = constructor.return_value
            client.responses.parse.return_value = type('Response', (), {
                'output_parsed': Answer(text='ok'), 'usage': None})()
            for _ in range(2):
                result = agent.handle(Task('test', 'hello', required_capabilities=('extract',)))
                self.assertEqual(result.output, {'text': 'ok'})
            constructor.assert_called_once()

    def test_multiple_capabilities_infer_registration_and_reject_duplicates(self):
        declaration = LlmCapability('extract', Prompt('Extract.', 'hello'), Answer)
        self.assertEqual(LlmAgent(handlers=[declaration]).capabilities, ['extract'])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            LlmAgent(handlers=[declaration, declaration])
        with self.assertRaisesRegex(ValueError, 'match'):
            LlmAgent(capabilities=['other'], handlers=[declaration])
