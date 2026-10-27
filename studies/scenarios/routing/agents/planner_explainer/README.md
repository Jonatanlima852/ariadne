# Planejador e explicador

Um `LlmAgent` com duas capacidades: `mission-planning` (planejador da missão)
e `explanation` (explica a rota escolhida). Implementação em [main.py](main.py).
O ID padrão é `planner-explainer-01`.

- [capabilities.py](capabilities.py): o prompt do planejador recebe o
  `PlannerRequest` (objetivo, contexto, histórico, capacidades disponíveis) e
  pede, na rodada 1, `PLAN` com o passo `route` (`route-planning`) e o passo
  `explain` (`explanation`, dependente de `route`, com a saída e o plano do
  BDI ligados por `input_bindings`); na rodada 2, `DONE` com
  `{route, distance, explanation}` copiados do histórico. O SDK valida a
  decisão (`PlannerDecision`) e monta a resposta do contrato.
- [response_models.py](response_models.py): formato validado da explicação.
- [substitute.py](substitute.py): substituto determinístico do provedor,
  ativado por `ROUTING_DEMO=1` ou `planner_explainer(demo=True)`. Troca só a
  chamada ao modelo; prompts, validação e protocolo são os mesmos. Serve a
  testes e demonstrações, não é uma linha de base.

Sem `ROUTING_DEMO`, o agente usa a OpenAI Responses API com `OPENAI_API_KEY`
e `LLM_MODEL`. Dependências vêm do projeto `sdk/python` (extra `llm`) ou da
imagem Docker. Execute módulos Python a partir da raiz do repositório.

[Cenário proprietário](../../README.md)
