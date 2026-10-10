# Código do SDK Python

`tg_sdk/` contém a API pública de agentes e cenários; `contract/` contém código
gerado do protobuf. Não edite os arquivos gerados manualmente.

Comece pelo [guia de desenvolvimento](../../../docs/development.md) e pelas
exportações de [tg_sdk](tg_sdk/__init__.py). Agentes novos implementam
`Agent.handle()`; `BdiAgent` e `LlmAgent` oferecem abstrações especializadas.

Para declarar BDI sem subclasse, use `BdiAgent`, `Input` e `Plan`; veja a
[referência de BDI e planejamento](../../../docs/bdi.md). `planning.py` fornece
busca genérica de custo uniforme; ações e restrições ficam no domínio.
