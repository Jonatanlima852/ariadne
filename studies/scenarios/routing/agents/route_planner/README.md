# Planejador de rotas

Planeja rotas com crenças e planos BDI.

Implementação em [main.py](main.py). O ID padrão é `route-planner-01`; cenários
podem configurar `AGENT_ID` para distinguir instâncias.

[Cenário proprietário](../../README.md)

A biblioteca de rotas fica em [plans.py](plans.py). O agente reutiliza esses
planos e mantém apenas a extração do desejo, as crenças externas e o tratamento do pedido de rota. A escolha por custo e o resultado ficam a cargo do SDK.

Dependências são fornecidas pelo projeto `sdk/python` (extra `llm` quando necessário)
ou pela imagem Docker. Execute módulos Python a partir da raiz do repositório.
