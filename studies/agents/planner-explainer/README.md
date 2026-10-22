# Planejador e explicador

Decompõe pedidos em workflows e explica os resultados com LLM. Também oferece interpretação e proposição de planos logísticos. Exige credencial do provedor.

Implementação em [main.py](main.py). O ID padrão é `planner-explainer-01`; cenários
podem configurar `AGENT_ID` para distinguir instâncias.

[Catálogo de agentes](../README.md)

## Como ler a implementação

- [main.py](main.py): compõe as quatro capacidades em um `LlmAgent`, sem herança.
- [workflow_capabilities.py](workflow_capabilities.py): prompts de decomposição e
  explicação e conversão do workflow para o formato consumido pelo runtime.
- [response_models.py](response_models.py): valida campos, limites e estrutura
  das respostas. Essas classes são contratos de dados, não classes de agentes.
- As capacidades logísticas vêm de
  [mission_assistant.py](../../scenarios/logistics/agents/mission_assistant.py),
  também utilizado diretamente pelo cenário logístico.

O SDK administra chamada ao provedor, resposta estruturada, erros, metadados e
registro no runtime. A configuração por ambiente continua disponível; testes
podem injetar `openai_client` sem fazer chamadas reais.
