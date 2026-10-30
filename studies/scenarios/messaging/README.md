# Mensageria

Dois agentes trocam um envelope pelo serviço de mensagens do runtime.

## Executar

Da raiz do repositório:

```sh
./ariadne run studies/scenarios/messaging/scenario.py
```

A entrada [scenario.py](scenario.py) declara `agent-a`, que publica um pedido
para `agent-b` com conversa, correlação e trace, e `agent-b`, que numa etapa
dependente recebe o envelope e devolve identificador, remetente, payload e
correlação. O resultado traz `matches_sent: true` quando o ID recebido é o
publicado. Os eventos do broker ficam em `message-events.jsonl`.

Este cenário determinístico demonstra um comportamento funcional; não mede,
isoladamente, a qualidade de raciocínio de uma LLM.

[Todos os estudos](../../README.md)
