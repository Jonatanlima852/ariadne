# Runtime Inspector

Interface React/Vite para consultar as evidências locais geradas pelo `ariadne`. O
frontend acessa uma API FastAPI somente leitura; nenhum comando shell ou ação
do Docker é disparado pela interface.

## Executar

Requisitos: Node 22 >=22.12 (linha usada no CI), npm e `uv`.
Intervalo aceito: `^20.19.0 || >=22.12.0`. Confira com
`./ariadne doctor --local --inspector`.

Na raiz do repositório, inicie a API:

```sh
npm run api --prefix tools/inspector
```

Em outro terminal, inicie o frontend:

```sh
npm ci --prefix tools/inspector
npm run dev --prefix tools/inspector
```

Abra `http://127.0.0.1:4173`. A tela lista automaticamente as execuções em
`.ariadne/runs`. O exemplo embutido continua disponível quando não houver uma
execução local.

Para ler outro diretório de execuções:

```sh
ARIADNE_RUNS_DIR=/caminho/para/runs npm run api --prefix tools/inspector
```

## API

As rotas disponíveis são:

- `GET /api/health`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events?after=0`
- `GET /api/runs/{run_id}/stream`

A API restringe a leitura aos arquivos de evidência reconhecidos dentro de
`.ariadne/runs` e limita cada resposta de execução a 20 MB.

## Verificar

```sh
npm test --prefix tools/inspector
npm run build --prefix tools/inspector
UV_CACHE_DIR=/tmp/ariadne-inspector-uv uv run --project tools/inspector/api --group dev pytest -q tools/inspector/api
```

[Roteiro para apresentar o trabalho](../../docs/presentation.md)
