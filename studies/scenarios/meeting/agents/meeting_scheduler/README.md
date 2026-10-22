# Agendador de reuniões

A implementação em [main.py](main.py) considera horário preferido, disponibilidade
e quórum parcial. Crenças e alternativas ficam em [beliefs.py](beliefs.py) e
[plans.py](plans.py). Sua capacidade é `meeting-scheduling`.

O [cenário local](../../scenario.py) usa a declaração mais simples em
[scheduler.py](../scheduler.py): exige todos os participantes e oferece `meeting`.
Ambas pertencem ao estudo de agendamento, com regras explicitamente diferentes.

Para iniciar este agente contra um Registry já disponível, da raiz:

```sh
uv run --project sdk/python python -m studies.scenarios.meeting.agents.meeting_scheduler.main
```

A configuração operacional usa AGENT_ID, AGENT_HOST, AGENT_PORT e REGISTRY_ADDR.
[Estudo de agendamento](../../README.md)
