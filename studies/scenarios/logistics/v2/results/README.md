# Resultados preservados da v2

A suíte básica e a suíte de estresse são preservadas separadamente, assim como
a coleta real e a demonstração de integração:

- **[Confirmação do híbrido enxuto: resultados e figuras](stress-lean/README.md)** — 60/60 observações, três repetições dos dez casos. Tempo médio 17,8 vezes menor, 94,4% menos tokens nos 29 pares com uso conhecido, 219/228 contra 204/228 pedidos entregues. [Resumo PNG](stress-lean/analysis/headline.png), [JSON](stress-lean/results.json) e [manifesto](stress-lean/manifest.json).
- [Suíte básica — LLM real: tabela](real/comparison.md), [resultados JSON](real/results.json) e [manifesto](real/manifest.json).
- [Suíte básica — demonstração determinística: tabela](demo/comparison.md), [resultados JSON](demo/results.json) e [manifesto](demo/manifest.json).

- [Estresse — demonstração determinística](stress-demo/comparison.md), [resultados JSON](stress-demo/results.json) e [manifesto](stress-demo/manifest.json).
- [Estresse — equipe original, coleta interrompida](stress-original-partial/comparison.md), [resultados JSON](stress-original-partial/results.json) e [manifesto](stress-original-partial/manifest.json). São 15/20 observações previstas, com sete pares completos e uma observação Single LLM sem par. Os totais dos grupos têm coberturas diferentes.

A [variante enxuta](../docs/lean.md) é uma configuração separada. Seus pilotos não
são incorporados à confirmação de três repetições. As figuras do fluxo ficam
em [presentation](presentation/README.md).
O [piloto enxuto](lean-development/comparison.md), com dois episódios, permanece
identificado como desenvolvimento e tem seu próprio manifesto e evidências.

Os dez [casos de estresse](../docs/stress.md) foram fixados antes das chamadas reais.
Coletas em andamento aparecem na aba **Logística v2** do Inspector; resultados
reais só são incorporados ao arquivo preservado após completar os pares previstos.

As duas configurações usam os mesmos casos e regras, com cada agente em seu próprio contêiner Docker. No modo real, todas as
chamadas usam `gpt-5.6-luna`; na demonstração não há chamadas a um modelo.
Os substitutos determinísticos usam políticas simbólicas também no lado
Single LLM e servem somente para conferir integração.

Os JSONs preservam estado final, histórico de ações e ocorrências, métricas,
resultados dos especialistas e metadados das chamadas. Foram removidas apenas
cópias repetidas de estado dos workflows e do retorno do executor. Cada
`evidence.json` informa o caminho local das evidências brutas e seu hash.
As evidências brutas incluem os eventos do runtime Go.

A tabela principal foi coletada depois de tornar explícita a regra herdada de
vias bidirecionais. Os LLMs recebem incidentes somente quando ocorrem. A coleta
exploratória anterior não entra nos resultados abaixo. Datas dos diretórios
são UTC; a execução ocorreu em 22/10/2026 no fuso America/Sao_Paulo.

A suíte básica original e as coletas de desenvolvimento têm uma observação por
caso/configuração; a confirmação enxuta tem três. Na equipe original, a latência
inclui OperationsReporter; a variante enxuta gera um resumo das métricas, sem
essa chamada. Os tempos excluem inicialização de serviços e agentes. Tokens são
os reportados pelo provedor; não estimamos preços. Os planos não são
necessariamente ótimos. Atendimento parcial nos casos de falta de estoque e
capacidade pode ser esperado, sem erro operacional. O único timeout da
confirmação permanece nos resultados; seu uso de tokens é desconhecido.

A conferência reproduziu os estados finais e métricas usando os históricos de
ações e as mesmas transições do domínio. Isso verifica consistência, sem alegar
um oráculo independente. Não foram criados testes automatizados.

## Totais da suíte básica original em Docker

| Configuração | Entregues | No prazo | Rejeitadas | Tempo somado (s) | Distância | Energia | Chamadas LLM | Tokens entrada / saída |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single-llm | 18/20 | 18 | 0 | 97.41 | 80 | 473 | 16 | 24023 / 8676 |
| ariadne | 18/20 | 18 | 0 | 267.47 | 76 | 467 | 38 | 69916 / 20337 |

A tabela detalhada por caso está em [real/comparison.md](real/comparison.md).
O tempo somado exclui a preparação dos contêineres. A demonstração determinística
continua separada e não entra nesses totais.

## Exportar análises e figuras

[Análise da suíte básica original](real/analysis/analysis.md) e
[análise dos pares da coleta original de estresse](stress-original-partial/analysis/analysis.md)
incluem CSVs e gráficos PNG/SVG. A coleta incompleta mantém a observação sem par
na tabela e a exclui das figuras comparativas.

```sh
uv run --no-project --with matplotlib python -m studies.scenarios.logistics.v2.benchmarks.analyze \
  --input studies/scenarios/logistics/v2/results/real/results.json \
  --output /tmp/logistics-analysis --title 'Logística: comparação medida'
```

O script não chama modelos nem altera os resultados de entrada. `--no-plots`
exporta somente CSV/Markdown sem matplotlib. As figuras mostram atendimento,
pontualidade, tempo real, tokens, distância e energia por caso, com número de
observações. Valores ausentes permanecem distintos de zero; modos e modelos
diferentes são rejeitados.
