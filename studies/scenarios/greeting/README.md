# Saudação LLM

Um agente LLM gera uma saudação estruturada, validada por um esquema.

## Pergunta

Um agente baseado em modelo de linguagem responde pelo contrato com saída
estruturada, sem classe nem decorator além de `LlmAgent`?

## Executar

```sh
export OPENAI_API_KEY=...
ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/greeting/scenario.py
```

Exige credencial e faz uma chamada real ao provedor, com custo. O executor
repassa `OPENAI_API_KEY` e `LLM_MODEL` ao contêiner do agente. A execução
fica em `runs/`.

## Variáveis

| Variável | Padrão | Efeito |
|---|---|---|
| `LLM_MODEL` | `gpt-5.6-luna` | Modelo pedido ao provedor |

## Limites

Uma chamada única; não há substituto determinístico nem avaliação de
qualidade da resposta.

[Todos os estudos](../../README.md)
