# Workflow sequencial explícito

Valida o primeiro incremento do engine de workflows sem LLM ou bindings:

```text
SubmitWorkflow
  first (echo)
    -> second (echo)
      -> WorkflowResult.output
```

## Execução recomendada

Com Docker e Compose >=2.24.4, na raiz:

```sh
./ariadne scenario workflow-sequential
```

O executor aguarda o agente, salva resultados e encerra o ambiente. Veja a
[referência](../../../../docs/cli.md) para `--keep`, logs e stop.

## Execução manual (Python e uv no host)

```sh
docker compose -f studies/scenarios/sequential_workflow/docker/compose.yaml \
  up --build -d --wait

uv run --project sdk/python python \
  studies/scenarios/sequential_workflow/docker/scenario.py

docker compose -f studies/scenarios/sequential_workflow/docker/compose.yaml down -v
```

O resultado esperado é `CENÁRIO APROVADO`. Os eventos no volume do
Orchestrator permitem reconstruir workflow, run, steps e tasks materializadas.

`down -v` apaga o volume de eventos deste cenário. Para preservá-lo, omita `-v`.

[Catálogo de cenários](../../../../docs/scenarios.md)
