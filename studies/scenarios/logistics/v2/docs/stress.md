# Suíte de estresse

A suíte básica mediu 18/20 entregas nas duas configurações. Seus episódios têm
1–3 pedidos em oito locais: o Single LLM resolve os pedidos viáveis e há pouco
espaço para que verificações simbólicas compensem interpretação, decomposição,
análise e relatório. Isso demonstra um custo da configuração, sem estabelecer
uma inferioridade geral do runtime.

A nova suíte em [cases_stress.json](../datasets/stress.json) foi fixada antes das
chamadas LLM reais. Amplia o mapa herdado para 16 locais, com 29 arestas,
conexões de mão única, quatro veículos e três depósitos. São cinco tipos de
item e 6–10 pedidos por episódio. As regras de validação e o modelo foram
preservados; os agentes continuam usando as arquiteturas LLM e BDI do SDK.
O mesmo mundo, limites e ocorrências são usados nas duas configurações.

| Caso | Pedidos | Mecanismo investigado |
|---|---:|---|
| s01-distributed-mixed-orders | 8 | Fontes de estoque, itens compostos e recursos distribuídos |
| s02-scarce-stock-coupling | 8 | Concorrência pelo mesmo SKU e exigência de um único depósito por pedido |
| s03-capacity-and-source | 8 | Peso composto e pedidos que exigem reutilizar o caminhão |
| s04-recharge-detours | 6 | Baterias baixas, acesso aos carregadores e desvios |
| s05-directed-connections | 6 | Mãos únicas e retorno diferente da ida |
| s06-progressive-roadblocks | 8 | Dois bloqueios durante a execução |
| s07-loaded-vehicle-loss | 6 | Pane e recuperação de carga com outro veículo |
| s08-cascading-disruptions | 10 | Pane e dois bloqueios em sequência, com trabalho pendente |
| s09-deadline-and-priority-pressure | 8 | Prazos apertados, carga e prioridades concorrentes |
| s10-infeasible-among-feasible | 8 | Identificar um pedido impossível e continuar os demais |

Há limites conhecidos antes da execução: em s02 a demanda de medicine é 10 e o
estoque total é 7; em s10, o1 pesa 21 e a capacidade máxima dos veículos é 20.
Esses fatos impedem atendimento total. Nos demais, não se presume uma solução
global ótima. A demonstração determinística fornece sequências verificáveis,
sem provar impossibilidade quando sua heurística não atende todos os pedidos.

A demonstração também expôs limitações da política simbólica: s04 e s08
terminaram parcialmente atendidos, e s09 teve atrasos. Os casos foram mantidos.
A finalidade é comparar confiabilidade e consumo com interações mais exigentes;
nenhuma configuração precisa vencer para que a comparação seja informativa.

```sh
# Comparar o híbrido enxuto ao Single LLM, com os contêineres no modo real:
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run \
  --suite stress --configurations single-llm ariadne-lean

# Mais observações dos mesmos casos, sem reescrever a suíte:
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run \
  --suite stress --repeat 3 --configurations single-llm ariadne-lean

# Executar as duas suítes:
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run \
  --suite all --configurations single-llm ariadne-lean
```

`ariadne` mantém a equipe original de dez especialistas; `ariadne-lean` usa
a [divisão enxuta de oito agentes](lean.md). Sem `--configurations`, o cliente
preserva o padrão histórico `single-llm ariadne`.

`--repeat` cria estados novos para cada episódio e alterna a ordem das
configurações entre repetições. Os processos dos agentes são reutilizados;
eles não guardam crenças de domínio entre tarefas. A suíte básica e seus
resultados anteriores permanecem disponíveis. Uma observação por caso é
exploratória e não estima a variabilidade do modelo em cada caso.

Na equipe original, o tempo principal inclui o relatório LLM. A variante enxuta
gera um resumo calculado das métricas, sem essa chamada. Nas novas coletas,
`wall_seconds_before_report` registra também o tempo até o resultado do domínio,
e `reporting_seconds` registra a fase do relatório. As colunas não substituem
o tempo completo nem ocultam o custo de explicar o resultado.

Abra `./ariadne inspect` e selecione **Logística v2**. O catálogo lê tanto as
coletas em `.ariadne/logistics-v2` quanto os resultados preservados em
`v2/results`. Há métricas por caso, gráficos interativos, entregas acumuladas,
ações, incidentes, prazos e respostas dos agentes. Use **Atualizar coleta**
para carregar novas observações de uma coleta em andamento.

A [confirmação concluída do híbrido enxuto](../results/stress-lean/README.md)
contém 60/60 observações, com três repetições dos dez casos: tempo médio 17,8
vezes menor, 94,4% menos tokens nos 29 pares com uso conhecido e 219/228 contra
204/228 pedidos entregues. O relatório preserva o timeout do Single LLM, o
caso de prazos em que ele foi melhor e os limites da comparação. Os casos
usados no desenvolvimento não constituem uma avaliação de generalização.
