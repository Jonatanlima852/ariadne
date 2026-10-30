# Fan-out: paralelismo e reatribuição no laço de missão

Estudo pequeno e determinístico, sem LLM, feito para mostrar na
apresentação o runtime acionando vários agentes em paralelo e reatribuindo um
passo quando o agente responsável não cumpre o prazo. Não é um benchmark de
modelo nem de domínio: a tarefa (contar palavras de um texto dividido em N
fragmentos, no estilo MapReduce) é propositalmente trivial.

## O que acontece numa execução

1. O cliente envia uma missão com o texto já dividido em N fragmentos
   (`context.shards`) e `max_parallel = K`.
2. O planejador determinístico (`mission-planning`) responde `PLAN` com N
   passos `map-i` (capacidade `fanout-count`, sem dependências entre si) e um
   passo `reduce` (`fanout-reduce`) que depende de todos e recebe cada saída
   por `input_bindings`.
3. O engine executa os `map-i` em ondas de até K passos. Cada contador dorme
   `work_ms` (trabalho simulado, 300 ms) e devolve as contagens do fragmento.
4. Com `FANOUT_FLAKY=1`, o agente `counter-flaky` oferece a mesma capacidade
   mas demora `3 × prazo`. A seleção `round_robin` garante que ele receba ao
   menos um passo; o orquestrador registra `TASK_TIMEOUT` ao fim do prazo
   (1500 ms) e, pela política `max_attempts=2, exclude_failed_agent=true`,
   emite `TASK_REASSIGNED` para outro contador, que conclui o passo.
5. O `reduce` soma as contagens; na rodada 2 o planejador responde `DONE`.

Agentes: `planner`, `counter-1..K`, `counter-flaky` (opcional), `reducer`.
N é no máximo 9 porque o validador do orquestrador aceita dez passos por
workflow e um deles é o `reduce`; o planejador descarta fragmentos além
disso e a configuração rejeita `FANOUT_SHARDS > 9`.

## Como executar

Da raiz (cada execução sobe seus contêineres):

```sh
# uma missão com os padrões: K=4, N=8, contador lento ligado
./ariadne run studies/scenarios/fanout/scenario.py

# cinco repetições; cada amostra fica em results.jsonl, a última em mission-result.json
./ariadne run studies/scenarios/fanout/scenario.py --repeat 5

# varredura de K sem o contador lento (speedup), 3 repetições por K, e a análise
uv run --project sdk/python python -m studies.scenarios.fanout.campaign \
  --workers 1 2 4 8 --repeat 3 --flaky 0 --output .ariadne/fanout/sweep

# análise de uma ou mais execuções (ou de uma campanha inteira)
uv run --project sdk/python python -m studies.scenarios.fanout.analysis \
  .ariadne/fanout/sweep/runs --output .ariadne/fanout/sweep/analysis
```

Variáveis: `FANOUT_WORKERS` (K, padrão 4), `FANOUT_SHARDS` (N, padrão 8),
`FANOUT_FLAKY` (1 liga o contador lento), `FANOUT_STEP_DEADLINE_MS` (1500),
`FANOUT_WORK_MS` (300), `FANOUT_FLAKY_FACTOR` (3). O prazo de passo chega ao
orquestrador como `EXECUTION_TIMEOUT`, definido por `mission.configure_runtime`
quando a declaração é carregada, porque o plano de uma missão não transporta
`deadline_ms` por passo.

A análise usa só a biblioteca padrão; com matplotlib disponível (por exemplo
`uv run --with matplotlib ...`) as figuras saem também em PNG. Os testes
estão em `tests/` (`test_mission.py` exige `ARIADNE_TEST_DOCKER=1`).

## Como ler as figuras

- `gantt-*.svg`: uma linha por agente, uma barra por tentativa, lida dos
  eventos do orquestrador (`TASK_ASSIGNED`/`TASK_REASSIGNED` até o término).
  Barras azuis são passos de mapa; a barra hachurada em vermelho é a
  tentativa que estourou o prazo no `counter-flaky`; a barra com contorno
  violeta é a tentativa 2 do mesmo passo em outro contador. As linhas
  tracejadas marcam o início das rodadas. Barras empilhadas na mesma coluna
  são passos executando ao mesmo tempo.
- `speedup.svg`: tempo de parede mediano por K e o speedup em relação ao
  menor K, com a reta ideal `min(K, N)`.
- `report.md`: tabelas com mediana, média, desvio e p95 do tempo de parede,
  do fator de paralelismo, da concorrência, dos tempos de recuperação e da
  completude do rastro.

Métricas (definições em `analysis.py`): fator de paralelismo = soma das
durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida
pelo intervalo entre o primeiro início e o último término; concorrência =
quantas tentativas rodavam ao mesmo tempo segundo os eventos; recuperação =
`TASK_REASSIGNED - TASK_TIMEOUT`; completude = eventos esperados presentes
sobre esperados (conjunto definido em `analysis.expected_events`).

## Resultados preservados

[results/2026-10-29](results/2026-10-29/README.md): K=4, N=8 com o contador
lento em cinco repetições; varredura K em {1, 2, 4, 8} sem o contador lento
(speedup 1,97, 3,82 e 7,04 para K = 2, 4 e 8); varredura K em {1, 2, 4} com o
contador lento. Recuperação mediana de 1,7 ms (p95 4,8 ms) em oito prazos
estourados; rastro completo em todas as vinte missões.

## O que o estudo mostra e o que não mostra

Mostra: o engine executa passos independentes em paralelo até `max_parallel`,
com speedup próximo do ideal para trabalho simulado homogêneo; o executor
detecta o prazo, reatribui a outro agente com a mesma capacidade em poucos
milissegundos e a missão completa com o resultado correto; cada etapa deixa
um evento, e o conjunto esperado está completo.

Não mostra: desempenho real de contagem de palavras (o trabalho é um
`sleep`), comportamento em vários hosts, falhas por perda de heartbeat ou
erro de aplicação (só prazo estourado), nem qualidade de deliberação. Um
limite visível nos Gantts: o engine despacha os passos em ondas de
`max_parallel` e espera a onda inteira terminar; enquanto a tentativa do
contador lento aguarda o prazo, os contadores livres ficam ociosos.

[Todos os estudos](../../README.md)
