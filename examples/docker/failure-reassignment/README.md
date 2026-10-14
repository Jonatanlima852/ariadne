# Cenário de timeout e reassignment

Este cenário valida timeout, exclusão de agente e nova atribuição:

```text
a-slow recebe a tentativa 1 -> timeout em 100 ms
orchestrator exclui a-slow -> redescobre agentes
b-healthy recebe a tentativa 2 -> COMPLETED
```

O Registry ordena agentes por ID, portanto `a-slow` é selecionado primeiro.

## Executar

Com Docker e Compose >=2.24.4, na raiz:

```sh
./ariadne scenario failure-reassignment
```

O executor aguarda os dois agentes, salva relatório e eventos e encerra sua
topologia. Veja a [referência](../../../docs/cli.md).

## Execução manual (Python e uv no host)

```sh
docker compose \
  -f examples/docker/failure-reassignment/compose.yaml \
  up --build -d --wait

uv run --directory sdk/python \
  python examples/docker/failure-reassignment/scenario.py
```

O resultado esperado contém `CENÁRIO APROVADO agent_id=b-healthy`.

Copie os eventos para medir timeout e recuperação:

```sh
docker compose -f examples/docker/failure-reassignment/compose.yaml \
  exec -T orchestrator cat /data/events.jsonl \
  > studies/runtime_metrics/results/failure-reassignment-events.jsonl
```

Encerre e remova os artefatos isolados:

```sh
docker compose -f examples/docker/failure-reassignment/compose.yaml down -v
```

`down -v` apaga o volume de eventos deste cenário. Para preservá-lo, omita `-v`.

[Catálogo de cenários](../../../docs/scenarios.md)
