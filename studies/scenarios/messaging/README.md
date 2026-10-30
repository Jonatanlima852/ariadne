# Mensageria

Dois agentes trocam um envelope pelo serviço de mensagens do runtime.

## Pergunta

Um agente consegue publicar um envelope para outro, com conversa, correlação
e trace preservados, e o destinatário recebê-lo numa etapa posterior?

## Executar

```sh
./ariadne run studies/scenarios/messaging/scenario.py
```

Em [scenario.py](scenario.py), `agent-a` publica um pedido para `agent-b`;
numa etapa dependente, `agent-b` recebe o envelope e devolve identificador,
remetente, payload e correlação. Resultado esperado: `matches_sent: true`. Os
eventos do broker ficam em `logs/message-events.jsonl` da execução, em `runs/`.

## Variáveis

Nenhuma.

## Limites

Cenário determinístico e sem LLM. A mensageria é em memória, com um stream
por destinatário e sem reentrega; não demonstra durabilidade.

[Todos os estudos](../../README.md)
