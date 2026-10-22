# Rotas

Investiga a cooperação para escolher e explicar um percurso: a LLM decompõe o
pedido, o BDI escolhe a rota e a LLM explica o resultado. O exemplo espera
`A → B → D`, distância 25. Não representa uma missão logística com bateria,
pacotes, chaves ou prazo; essas regras pertencem a [logistics](../logistics/README.md).

- [scenario.py](scenario.py): cliente de integração do fluxo completo.
- [agents/route_planner](agents/route_planner/README.md): crenças e planos de rotas.
- [agents/planner_explainer](agents/planner_explainer/README.md): decomposição e explicação.
- [docker](docker/README.md): configuração e execução dos serviços.
- [benchmarks](benchmarks/README.md): medição C, dentro deste assunto.

Da raiz, com a credencial LLM configurada:

```sh
./ariadne scenario heterogeneous-route
```

O nome público do comando foi preservado. `scenario.py` usa `RuntimeClient`,
portanto não é uma declaração para `./ariadne run`.
A escolha BDI isolada é coberta por testes funcionais, sem benchmark próprio.

[Todos os estudos](../../README.md)
