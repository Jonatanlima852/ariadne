# Agentes compartilhados

`text.py` oferece fábricas `echo_agent` e `uppercase_agent`, usadas por tarefa
simples, workflow e recuperação. Cada cenário instancia os participantes e
configura nomes e atrasos; não copia a implementação do comportamento.

Os nomes descrevem responsabilidades. BDI e LLM identificam a arquitetura,
não a identidade do participante.

| Agente | Responsabilidade | Implementação |
|---|---|---|
| [route-planner](route-planner/README.md) | Planejar rotas; também expõe execução de missões logísticas | BDI |
| [planner-explainer](planner-explainer/README.md) | Decompor pedidos em tarefas e explicar resultados; também expõe capacidades logísticas | LLM |
| [meeting-scheduler](meeting-scheduler/README.md) | Encontrar um horário compatível com as agendas | BDI |
| [text-echo](text-echo/README.md) | Devolver o texto recebido | Determinística |
| [execution-simulator](execution-simulator/README.md) | Simular execução, atraso, falhas probabilísticas e carga reportada | Simulação controlada |
| [failure-simulator](failure-simulator/README.md) | Falhar intencionalmente em toda tarefa | Simulação controlada |

Os agentes específicos de logística ficam em
[mission_planner.py](../scenarios/logistics/agents/mission_planner.py) e
[mission_assistant.py](../scenarios/logistics/agents/mission_assistant.py).
O primeiro planeja a missão estruturada; o segundo interpreta pedidos e propõe planos.
IDs padrão e nomes dos serviços Docker também refletem essas responsabilidades.
Evidências históricas preservam os nomes e IDs originais da coleta.

Agentes usados exclusivamente por um cenário ficam no próprio cenário. Os
primitivos genéricos (`Agent`, `BdiAgent`, `LlmAgent`) pertencem ao SDK.

[Estudos](../README.md)
