# Workflow sequencial

Uma etapa devolve texto; outra recebe esse resultado e o transforma em maiúsculas.

## Executar

Da raiz do repositório:

```sh
./ariadne run studies/scenarios/sequential_workflow/scenario.py
```

A definição está em [scenario.py](scenario.py). O SDK registra os resultados e
eventos em `.ariadne/runs/`; abra-os com `./ariadne inspect`.

Este cenário determinístico demonstra um comportamento funcional; não mede,
isoladamente, a qualidade de raciocínio de uma LLM.

[Todos os estudos](../../README.md)
