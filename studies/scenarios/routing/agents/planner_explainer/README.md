# Planejador e explicador

Decompõe pedidos em workflows e explica os resultados com LLM. Exige credencial do provedor.

Implementação em [main.py](main.py). O ID padrão é `planner-explainer-01`; cenários
podem configurar `AGENT_ID` para distinguir instâncias.

[Cenário proprietário](../../README.md)

## Como ler a implementação

- [main.py](main.py): compõe as duas capacidades em um `LlmAgent`, sem herança.
- [workflow_capabilities.py](workflow_capabilities.py): prompts de decomposição e
  explicação e conversão do workflow para o formato consumido pelo runtime.
- [response_models.py](response_models.py): valida campos, limites e estrutura
  das respostas. Essas classes são contratos de dados, não classes de agentes.

O SDK administra chamada ao provedor, resposta estruturada, erros, metadados e
registro no runtime. A configuração por ambiente continua disponível; testes
podem injetar `openai_client` sem fazer chamadas reais.

Dependências são fornecidas pelo projeto `sdk/python` (extra `llm` quando necessário)
ou pela imagem Docker. Execute módulos Python a partir da raiz do repositório.
