# Agendador de reuniões

A implementação em [main.py](main.py) é um `BdiAgent` deliberativo do SDK:
as agendas em [beliefs.py](beliefs.py) são as crenças iniciais, o objetivo
`schedule_meeting` leva participantes, duração e horário preferido lidos do
payload, e os `GoalPlan`s em [plans.py](plans.py) competem por custo
(horário preferido, primeiro horário com todos, quórum parcial, sem horário).
Sua capacidade é `meeting-scheduling`; o resultado traz o plano escolhido e o
rastro de deliberação.

O [cenário](../../scenario.py) o declara diretamente; `./ariadne run` o sobe
em seu contêiner.

[Estudo de agendamento](../../README.md)
