# Testes do SDK

Cobrem modelos Python/protobuf, API de autoria, saída LLM com cliente falso,
mensageria e chamadas de cenários. Não exigem serviços ativos ou chave de LLM.

Da raiz do repositório:

```sh
uv run --directory sdk/python --with pytest python -m pytest tests -q
```

Para outras verificações e integrações, veja o
[guia de desenvolvimento](../../../docs/development.md#preparar-e-verificar).

As verificações novas de descrição e handler usam `unittest`:

```sh
uv run --directory sdk/python python -m unittest discover -s tests -q
```

Após preparar os binários com `./tg run examples/echo.py`, execute da raiz
as integrações reais opt-in (abrem portas locais, sem LLM nem Docker):

```sh
TG_TEST_RUNTIME_DIR="$PWD/.tg/bin" uv run --project sdk/python \
  python -m unittest discover -s sdk/python/tests -q
```

Cobrem bindings, repetições, BDI, reassignment, erros, startup parcial,
interrupção, execução fora do checkout e execuções simultâneas.

`test_declarative_bdi.py` verifica seleção sem efeitos dos candidatos descartados,
isolamento concorrente, entradas e evidências de falha. `test_planning.py` cobre
caminhos de menor custo, ciclos, desempates e limites da busca. As integrações
executam rotas e agendamento pela mesma API BDI, além do estudo logístico.
