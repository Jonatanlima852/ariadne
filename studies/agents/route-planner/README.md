# Planejador de rotas

Planeja rotas com crenças e planos BDI. Também oferece `logistics-execution`, delegando às regras do cenário logístico.

Implementação em [main.py](main.py). O ID padrão é `route-planner-01`; cenários
podem configurar `AGENT_ID` para distinguir instâncias.

[Catálogo de agentes](../README.md)

A biblioteca de rotas fica em [plans.py](plans.py). O agente reutiliza esses
planos e mantém apenas a extração do desejo, as crenças externas e a adaptação
da missão logística. A escolha por custo e o resultado ficam a cargo do SDK.
