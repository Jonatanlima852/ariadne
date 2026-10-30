# Recuperação por nova atribuição

Dois agentes oferecem a mesma capacidade; um deles demora mais que o prazo
da etapa e o runtime reatribui a tarefa ao outro.

## Pergunta

Com `deadline_ms`, `max_attempts=2` e `exclude_failed_agent`, o runtime
detecta o prazo estourado e conclui a tarefa em outro agente?

## Executar

```sh
./ariadne run studies/scenarios/failure_reassignment/scenario.py
```

Resultado esperado: concluído por `b-healthy`, com `TASK_TIMEOUT` e
`TASK_REASSIGNED` em `events.jsonl`. A execução fica em `runs/`, ao lado
deste README; [tools/runtime_metrics](../../../tools/runtime_metrics/README.md)
extrai os tempos de recuperação dos eventos.

## Variáveis

Nenhuma.

## Limites

Cenário determinístico e sem LLM. Um timeout não garante que o agente lento
tenha interrompido efeitos externos; só a falha por prazo é exercitada.

[Todos os estudos](../../README.md)
