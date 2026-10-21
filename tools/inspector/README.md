# Ariadne Inspector

Interface React/Vite e API FastAPI somente leitura para explorar evidências do
runtime. Não executa agentes, campanhas ou avaliações. Não usa o stream de
produção: o replay é uma reprodução manual dos eventos salvos.

## Abrir com um comando

Requisitos: uv, npm e Node `^20.19.0 || >=22.12.0`. O CI usa a versão de `.nvmrc`.
Da raiz do checkout:

```sh
./ariadne doctor --local --inspector
./ariadne inspect
```

Abra `http://127.0.0.1:4173`. O supervisor prepara o frontend com `npm ci` quando
faltam dependências ou muda o lock, inicia API e Vite e verifica prontidão.
Ctrl+C encerra ambos; falha de um processo também encerra o outro. Os logs ficam
em `.ariadne/inspector/ID/`. Portas ocupadas produzem erro, sem parar serviços alheios.

```sh
./ariadne inspect --port 4175 --api-port 8789
./ariadne inspect --runs-dir .tg/runs --campaigns-dir .tg/campaigns
```

`--evaluations-dir` também seleciona outra raiz. As variáveis `ARIADNE_RUNS_DIR`,
`ARIADNE_CAMPAIGNS_DIR` e `ARIADNE_EVALUATIONS_DIR` são reconhecidas pela API.
O supervisor escuta somente em localhost e não abre o navegador automaticamente.

## Explorar

- **Execuções:** busca por nome, caso, estratégia ou ID, filtro por estado,
  data e paginação. A URL local identifica fonte, execução, amostra e aba.
- **Amostras:** `results.jsonl` permite escolher cada repetição. Eventos são
  filtrados por trace, preservando números de linha e arquivos originais.
- **Workflow e replay:** conexões vêm de `manifest.json`, incluindo ramificações.
  Clique na etapa para ver entrada declarada, bindings e resultado. Avance por
  evento para acompanhar atribuição, timeout e reassignment. O resultado final
  fica identificado como tal e não representa o estado intermediário do replay.
- **Resultados:** estado operacional, decisão de viabilidade e avaliação de
  domínio são dimensões distintas. Sem avaliação, a interface não presume validade.
- **Campanhas:** filtre caso, estratégia e repetição; abra uma observação. Falhas
  sem arquivos continuam visíveis. A interface apresenta registros e total previsto.
- **Avaliações:** leia tabelas e respostas já calculadas pelo avaliador logístico.
  A otimalidade agregada inclui rejeições corretas; observe cobertura e limitações.
- **Demonstrações:** echo, workflow com duas amostras, recuperação e avaliação
  histórica BDI/LLM/híbrido. Veja [origem dos exemplos](samples/README.md).
- **Dados brutos:** arquivos integrais, incluindo amostras não selecionadas.

Avaliações são associadas a execuções/campanhas pelos caminhos de entrada
registrados. Na execução, selecione a análise para consultar o julgamento da
amostra. Mover os dados pode quebrar essa associação; a análise continua disponível
separadamente. A interface não recalcula métricas nem valida novamente a proveniência.

Execuções antigas sem manifesto não têm setas inferidas. Mensagens são mostradas
na tela de resultados; o grafo representa dependências de tarefas, não mensageria.
O exemplo embutido de recuperação continua disponível mesmo sem API.

## Desenvolvimento manual

```sh
npm ci --prefix tools/inspector
npm run api --prefix tools/inspector
# Em outro terminal:
npm run dev --prefix tools/inspector
```

API: porta 8787; frontend: 4173. `ARIADNE_INSPECTOR_API_PORT` configura o proxy Vite.

## API e limites

- `GET /api/catalog?source=runs|campaigns|evaluations|samples&q=...&status=...&offset=0&limit=20`
- `GET /api/evidence?source=...&identifier=...`
- `GET /api/health`

As rotas anteriores `/api/runs`, `/api/runs/{id}`, `/events` e `/stream` permanecem.
O novo fluxo não usa o cursor dessas rotas. Fontes ficam restritas às raízes
configuradas; links simbólicos não são seguidos pelo catálogo novo. Respostas de
execução têm limite de 20 MB; dados maiores exigem exploração pelos arquivos locais.
O catálogo é paginado, mas ainda percorre os diretórios para filtrar e ordenar.

## Verificar

`make verify` inclui parser, supervisor, API e build, sem testes de navegador.
Verificações isoladas:

```sh
npm test --prefix tools/inspector
npm run build --prefix tools/inspector
uv run --project sdk/python python -m unittest discover -s tools/inspector -p 'test_serve.py'
uv run --project tools/inspector/api --group dev pytest -q tools/inspector/api
```

[Roteiro de apresentação](../../docs/presentation.md)
