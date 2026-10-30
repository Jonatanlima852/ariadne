# Seleção de agentes

Compara FIRST_AVAILABLE, ROUND_ROBIN e LEAST_LOADED entre três trabalhadores
aptos para a mesma tarefa. As cargas reportadas são controladas (0,7; 0,1; 0,4),
portanto não representam medições de uso de CPU.

```sh
./ariadne run studies/scenarios/agent_selection/scenario.py
POLICY=LEAST_LOADED ./ariadne run studies/scenarios/agent_selection/scenario.py
```

A entrada [scenario.py](scenario.py) declara os três agentes e nove tarefas;
`POLICY` escolhe a política. Os eventos `TASK_ASSIGNED` de `events.jsonl`
mostram a distribuição. Nenhuma execução usa LLM.

[Todos os estudos](../../README.md)
