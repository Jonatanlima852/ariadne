# Agendador de reuniões

A implementação em [main.py](main.py) é um `BdiAgent` deliberativo do SDK:
as agendas em [beliefs.py](beliefs.py) são as crenças iniciais, o objetivo
`schedule_meeting` leva participantes, duração e horário preferido lidos do
payload, e os `GoalPlan`s em [plans.py](plans.py) competem por custo
(horário preferido, primeiro horário com todos, quórum parcial, sem horário).
Sua capacidade é `meeting-scheduling`; o resultado traz o plano escolhido e o
rastro de deliberação.

O [cenário local](../../scenario.py) usa a declaração mais simples em
[scheduler.py](../scheduler.py): exige todos os participantes e oferece `meeting`.
Ambas pertencem ao estudo de agendamento, com regras explicitamente diferentes.

Para iniciar este agente contra um Registry já disponível, da raiz:

```sh
uv run --project sdk/python python -m studies.scenarios.meeting.agents.meeting_scheduler.main
```

A configuração operacional usa AGENT_ID, AGENT_HOST, AGENT_PORT e REGISTRY_ADDR.
[Estudo de agendamento](../../README.md)
