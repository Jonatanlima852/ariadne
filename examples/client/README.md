# Cenário heterogêneo LLM + BDI

Este cenário usa a API pública `tg_sdk.Scenario` para enviar uma pergunta ao
runtime, que coordena o planejamento e a execução das etapas:

```text
LLM decompõe -> BDI planeja rota -> LLM explica
```

Suba os serviços:

```sh
docker compose --env-file .env \
  -f tools/deploy/docker-compose.yml \
  --profile heterogeneous \
  up --build -d
```

Execute:

```sh
uv run --project sdk/python \
  python examples/client/heterogeneous_demo.py
```

O cenário aprova somente se o BDI selecionar `via_intermediate`,
retornar a rota `A -> B -> D` e distância `25`.

O arquivo do cenário trabalha apenas com valores Python. Construção de
protobuf, IDs, trace compartilhado, conexão gRPC e submissão ao orchestrator
ficam encapsulados pelo SDK.

O encadeamento ocorre no Orchestrator: o planner obtém um DAG, o runtime valida
as dependências e bindings e executa os steps de rota e explicação. O cliente
recebe `ScenarioWorkflowResult` e salva o relatório correlacionado.

Para uma topologia dedicada com instruções completas de configuração e
encerramento, prefira o [guia do cenário](../docker/heterogeneous-route/README.md).
Veja também a [arquitetura](../../docs/architecture.md).
