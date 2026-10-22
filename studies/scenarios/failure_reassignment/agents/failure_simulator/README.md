# Simulador de falha

Retorna uma falha intencional em toda tarefa, permitindo observar a política de recuperação do runtime.

Implementação em [main.py](main.py). O ID padrão é `failure-simulator-01`; cenários
podem configurar `AGENT_ID` para distinguir instâncias.

[Cenário proprietário](../../README.md)

Dependências são fornecidas pelo projeto `sdk/python` (extra `llm` quando necessário)
ou pela imagem Docker. Execute módulos Python a partir da raiz do repositório.
