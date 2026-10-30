# Agendamento BDI

Um agente BDI deliberativo escolhe um horário compatível com as agendas e o
mais próximo possível do horário preferido.

## Pergunta

Um agente com crenças (agendas), um objetivo com parâmetros e planos que
competem por custo resolve a tarefa pela mesma interface que os demais, com
rastro de deliberação no resultado?

## Executar

```sh
./ariadne run studies/scenarios/meeting/scenario.py
```

Resultado esperado: `start_hour: 12` com os três participantes, plano
`earliest_full_slot` (13h é o preferido, mas carol está ocupada). O agente
[meeting_scheduler](agents/meeting_scheduler/README.md) usa `BdiAgent` com
`GoalPlan`: as agendas em `beliefs.py` são as crenças, o objetivo
`schedule_meeting` lê participantes, duração e horário preferido do payload
e os planos em `plans.py` (horário preferido, primeiro horário com todos,
quórum parcial, sem horário) competem por custo. O plano escolhido e o
`bdi_trace` ficam em `metadata` do resultado, em `runs/`; o mesmo rastro vai
em `TaskResult.bdi` do contrato.

## Variáveis

Nenhuma.

## Limites

Cenário determinístico e sem LLM. O BDI é uma abstração simplificada, não um
interpretador AgentSpeak; as agendas são fixas no código.

[Todos os estudos](../../README.md)
