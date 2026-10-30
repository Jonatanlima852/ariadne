# Tarefa simples

Descoberta, atribuição e resposta de um agente de eco.

## Executar

Da raiz do repositório:

```sh
./ariadne run studies/scenarios/basic_task/scenario.py
```

A definição está em [scenario.py](scenario.py). O SDK registra os resultados e
eventos em `runs/`, ao lado deste README.

Campanha de repetições independentes: `./ariadne campaign studies/scenarios/basic_task/benchmarks/campaign.py`.

Este cenário determinístico demonstra um comportamento funcional; não mede,
isoladamente, a qualidade de raciocínio de uma LLM.

[Todos os estudos](../../README.md)
