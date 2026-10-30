# Saudação LLM

Geração de uma saudação estruturada usando o provedor configurado.

## Executar

Da raiz do repositório:

```sh
ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/greeting/scenario.py
```

A definição está em [scenario.py](scenario.py). O SDK registra os resultados e
eventos em `.ariadne/runs/`.

Requer credencial do provedor para as etapas LLM e pode gerar custos.

[Todos os estudos](../../README.md)
