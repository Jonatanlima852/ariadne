# Rotas BDI

Seleção de um plano de menor custo entre rotas declaradas.

## Executar

Da raiz do repositório:

```sh
./ariadne run studies/scenarios/bdi_route/scenario.py
```

A definição está em [scenario.py](scenario.py). O SDK registra os resultados e
eventos em `.ariadne/runs/`; abra-os com `./ariadne inspect`.

Este cenário determinístico demonstra um comportamento funcional; não mede,
isoladamente, a qualidade de raciocínio de uma LLM.

[Todos os estudos](../../README.md)
