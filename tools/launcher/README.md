# Implementação do executor

[`tg`](../../tg) é o bootstrap da CLI Python. O backend [docker.sh](docker.sh)
combina o Compose de
cada cenário, um override por execução e [runner.compose.yaml](runner.compose.yaml).
O override remove portas do host e permite reinício após falha de inicialização.
`runner.py` espera pelos agentes e executa os scripts originais via `runpy`.

Uma descrição separada `control.yaml` permite exportação, logs e encerramento
por projeto sem depender de credenciais ou do arquivo `.env` original.
Se a exportação dos eventos falhar, a limpeza preserva o volume para recuperação.

## Verificações

Da raiz, com o ambiente do SDK disponível:

```sh
uv run --directory sdk/python python -m unittest discover -s ../../tools/launcher -p 'test_*.py'
```

Os testes do shell usam um Docker falso em diretórios temporários. Cobrem
isolamento, sucesso, falha, `--keep`, stop, cancelamento e limpeza. Os testes
de prontidão usam stubs e relógio controlado, sem serviços externos.

Para verificar o caminho integrado determinístico, use `./tg demo` e os
cenários workflow-sequential, failure-reassignment e messaging-basic.
`doctor` dos cenários LLM valida configuração, não realiza inferência.

[Guia público](../../docs/cli.md)
