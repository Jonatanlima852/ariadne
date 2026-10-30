# Workflow sequencial

Uma etapa devolve texto; outra recebe esse resultado por binding e o
transforma em maiúsculas.

## Pergunta

O runtime executa um DAG de etapas, transferindo a saída de uma para a
entrada da outra sem que os agentes se conheçam?

## Executar

```sh
./ariadne run studies/scenarios/sequential_workflow/scenario.py
```

Resultado esperado: `{"text": "OLÁ, AGENTES!"}`. Em [scenario.py](scenario.py),
`first.output["text"]` declara o binding e a dependência. A execução fica em
`runs/`, ao lado deste README.

## Variáveis

Nenhuma.

## Limites

Cenário determinístico e sem LLM. Demonstra bindings e ordem; não mede
desempenho.

[Todos os estudos](../../README.md)
