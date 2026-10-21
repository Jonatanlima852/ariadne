# Recuperação por nova atribuição

Uma tentativa ultrapassa o prazo; o runtime seleciona outro agente.

## Executar

Da raiz do repositório:

```sh
./ariadne run studies/scenarios/failure_reassignment/scenario.py
```

A definição está em [scenario.py](scenario.py). O SDK registra os resultados e
eventos em `.ariadne/runs/`; abra-os com `./ariadne inspect`.

[Execução e configuração Docker](docker/README.md).

[Métricas de recuperação](runtime_metrics/README.md). Um timeout não garante que
o agente anterior tenha interrompido efeitos externos.

Este cenário determinístico demonstra um comportamento funcional; não mede,
isoladamente, a qualidade de raciocínio de uma LLM.

[Todos os estudos](../../README.md)
