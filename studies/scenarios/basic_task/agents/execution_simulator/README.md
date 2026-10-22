# Simulador de execução

Simula duração, falha probabilística e carga reportada para estudar seleção e recuperação. Não interpreta o domínio da tarefa. Configure `DELAY_MS`, `FAIL_RATE` e `REPORTED_LOAD`.

Implementação em [main.py](main.py). O ID padrão é `execution-simulator-01`; cenários
podem configurar `AGENT_ID` para distinguir instâncias.

[Cenário proprietário](../../README.md)

Dependências são fornecidas pelo projeto `sdk/python` (extra `llm` quando necessário)
ou pela imagem Docker. Execute módulos Python a partir da raiz do repositório.
