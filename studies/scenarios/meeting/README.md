# Agendamento BDI

Um agente BDI escolhe um horário compatível com as agendas e a preferência
declaradas.

## Pergunta

Um agente com crenças, restrições e planos de custo resolve a tarefa pela
mesma interface que os demais?

## Executar

```sh
./ariadne run studies/scenarios/meeting/scenario.py
```

Resultado esperado: `start: 12`. [scenario.py](scenario.py) usa a API
declarativa (`Plan`); o agente [meeting_scheduler](agents/meeting_scheduler/README.md)
usa o ciclo de deliberação (`GoalPlan`) com as mesmas regras de custo. O
rastro BDI fica em `metadata` do resultado, em `runs/`.

## Variáveis

Nenhuma.

## Limites

Cenário determinístico e sem LLM. O BDI é uma abstração simplificada, não um
interpretador AgentSpeak.

[Todos os estudos](../../README.md)
