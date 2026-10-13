# Exemplos de agentes BDI

As implementações executáveis estão no [agente de rotas](../support/agents/bdi-agent/main.py)
e no [agendador de reuniões](../support/agents/meeting-scheduler/main.py).
Este diretório funciona como ponto de navegação; não contém outro worker.

Para observar deliberação local sem Docker, execute da raiz:

```sh
uv run --directory sdk/python python ../../examples/support/agents/meeting-scheduler/demo.py
```

Veja o [catálogo de cenários](../../docs/scenarios.md) para integrar BDI ao runtime
e o [guia de desenvolvimento](../../docs/development.md) para a API de autoria.
