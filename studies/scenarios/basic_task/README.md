# Tarefa simples

Um agente de eco recebe uma tarefa e devolve o texto. É o menor cenário do
repositório e o primeiro a rodar.

## Pergunta

O runtime descobre um agente pela capacidade, atribui a tarefa e devolve a
resposta ao cliente?

## Executar

```sh
./ariadne run studies/scenarios/basic_task/scenario.py
```

Resultado esperado: `WORKFLOW_STATUS_COMPLETED` com `{"text": "Olá, Ariadne!"}`.
A execução fica em `runs/`, ao lado deste README; `events.jsonl` mostra
`TASK_ASSIGNED` e `TASK_COMPLETED` para o agente `echo`.

## Variáveis

Nenhuma.

## Repetir e analisar

`./ariadne campaign studies/scenarios/basic_task/campaign.py` faz três
execuções independentes. Não há análise própria: compare os `summary.json`.

## Limites

Cenário determinístico e sem LLM. Demonstra o caminho operacional, não mede
qualidade de raciocínio nem overhead do runtime.

[Todos os estudos](../../README.md)
