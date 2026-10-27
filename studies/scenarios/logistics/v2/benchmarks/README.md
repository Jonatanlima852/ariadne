# Campanhas e avaliação da logística v2

Execute os módulos a partir da raiz do repositório:

| Módulo | Responsabilidade |
|---|---|
| `run` | Executar casos contra os agentes registrados no runtime Docker |
| `archive` | Reproduzir transições, conferir métricas e preservar uma coleta |
| `analyze` | Exportar CSV, Markdown e gráficos de resultados existentes |
| `summary_slide` | Gerar a figura de resumo de uma coleta real pareada |

```sh
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run --help
python3 -m studies.scenarios.logistics.v2.benchmarks.analyze \
  --input studies/scenarios/logistics/v2/results/real/results.json \
  --output /tmp/logistics-analysis --no-plots
```

`run` precisa dos serviços descritos no [guia Docker](../docker/README.md).
`analyze --no-plots` usa somente a biblioteca padrão; gráficos e
`summary_slide` requerem matplotlib. `archive` usa o SDK e verifica o histórico
antes de gravar, recusando sobrescrever uma coleção existente.

Os dados de entrada permanecem em `../datasets/`; domínio, agentes e políticas
ficam em `../domain/`, `../execution/` e `../agents/`. Coletas novas são gravadas em
`.ariadne/logistics-v2/`; os [resultados selecionados](../results/README.md)
mantêm seus caminhos para preservar referências e proveniência.

Os manifestos antigos registram os nomes dos módulos antes desta organização.
Esses registros e os hashes de coleta são históricos e não devem ser atualizados
para corresponder ao código atual. Os comandos atuais usam `.v2.benchmarks`.

O `.gitignore` permite as coleções selecionadas existentes e ignora novos
diretórios locais em `results/`. Para publicar outra coleção, inclua sua exceção
explicitamente. O diagnóstico local `results/containers.jsonl` permanece no
disco, fora do versionamento.
