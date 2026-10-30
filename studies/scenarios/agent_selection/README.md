# Seleção de agentes

Três agentes aptos para a mesma tarefa, com cargas reportadas controladas
(0,7; 0,1; 0,4), recebem nove tarefas segundo a política escolhida.

## Pergunta

As políticas `FIRST_AVAILABLE`, `ROUND_ROBIN` e `LEAST_LOADED` distribuem as
tarefas de forma diferente entre agentes equivalentes?

## Executar

```sh
./ariadne run studies/scenarios/agent_selection/scenario.py
AGENT_SELECTION_POLICY=LEAST_LOADED ./ariadne run studies/scenarios/agent_selection/scenario.py
```

Os eventos `TASK_ASSIGNED` de `events.jsonl`, em `runs/`, mostram a
distribuição por agente.

## Variáveis

| Variável | Padrão | Efeito |
|---|---|---|
| `AGENT_SELECTION_POLICY` | `ROUND_ROBIN` | Política das nove tarefas: `FIRST_AVAILABLE`, `ROUND_ROBIN`, `LEAST_LOADED` ou `RANDOM` |

## Limites

As cargas são declaradas pelos agentes, não medidas. Cenário determinístico
e sem LLM.

[Todos os estudos](../../README.md)
