# Cenário de mensageria básica

Valida o caminho mínimo `agent-a -> MessagingService -> agent-b`, incluindo
payload, conversation, correlation, trace, task e TTL.

## Execução recomendada

Com Docker e Compose >=2.24.4, na raiz:

```sh
./ariadne scenario messaging-basic
```

O executor salva a mensagem recebida e os eventos antes de encerrar sua
topologia. Veja a [referência](../../../../docs/cli.md).

## Execução manual (Python e uv no host)

```sh
docker compose -f studies/scenarios/messaging/docker/compose.yaml up --build -d --wait

PYTHONPATH=sdk/python/src \
uv run --project sdk/python \
  python studies/scenarios/messaging/scenario.py

docker compose -f studies/scenarios/messaging/docker/compose.yaml down
```

O cenário deve terminar com `CENÁRIO APROVADO`. O broker é em memória e possui
semântica at-most-once; mensagens pendentes não sobrevivem a reinício.

[Catálogo de cenários](../../../../docs/scenarios.md)
