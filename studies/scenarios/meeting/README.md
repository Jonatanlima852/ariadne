# Agendamento BDI

Escolha de horário compatível com agendas e preferência declaradas.

## Executar

Da raiz do repositório:

```sh
./ariadne run studies/scenarios/meeting/scenario.py
```

A definição está em [scenario.py](scenario.py), com a API declarativa (`Plan`).
O agente [meeting_scheduler](agents/meeting_scheduler/README.md)
usa o ciclo de deliberação (`GoalPlan`) com as mesmas regras de custo. O SDK
registra os resultados e eventos em `.ariadne/runs/`; abra-os com `./ariadne inspect`.

Este cenário determinístico demonstra um comportamento funcional; não mede,
isoladamente, a qualidade de raciocínio de uma LLM.

[Todos os estudos](../../README.md)
