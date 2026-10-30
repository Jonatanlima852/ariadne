# Estudo de paralelismo e reatribuição: relatório

## Execuções analisadas

| Execução | Grupo | Amostras |
|---|---|---:|
| `ariadne-33aa4a008a774218aeb27536466fa361` | K=8 N=8 no-flaky | 3 |
| `ariadne-3a0af95626294100bfa574dfc4c309ee` | K=2 N=8 no-flaky | 3 |
| `ariadne-4da0e8cd7b964693bd987b112c72d0b4` | K=1 N=8 no-flaky | 3 |
| `ariadne-b1b0aa110daf40d0b22f192736ce9949` | K=4 N=8 no-flaky | 3 |

## Por grupo (K trabalhadores, N fragmentos, contador lento)

| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |
|---|---:|---|---|---|---|---:|---:|
| K=8 N=8 no-flaky | 3/3 | mediana 351.5, média 355.3, desvio 11.7, p95 368.4 (n=3) | mediana 7.88, média 7.88, desvio 0.05, p95 7.94 (n=3) | mediana 7.72, média 7.71, desvio 0.04, p95 7.74 (n=3) | 8 / 7.89 | 0 / 0 | 100.0% mín., 100.0% média |
| K=2 N=8 no-flaky | 3/3 | mediana 1293.7, média 1292.9, desvio 2.6, p95 1295.0 (n=3) | mediana 1.97, média 1.97, desvio 0.00, p95 1.97 (n=3) | mediana 1.96, média 1.96, desvio 0.00, p95 1.96 (n=3) | 2 / 1.99 | 0 / 0 | 100.0% mín., 100.0% média |
| K=1 N=8 no-flaky | 3/3 | mediana 2568.5, média 2556.7, desvio 20.8, p95 2568.9 (n=3) | mediana 0.98, média 0.98, desvio 0.00, p95 0.98 (n=3) | mediana 0.98, média 0.98, desvio 0.00, p95 0.98 (n=3) | 1 / 0.99 | 0 / 0 | 100.0% mín., 100.0% média |
| K=4 N=8 no-flaky | 3/3 | mediana 668.6, média 668.2, desvio 10.4, p95 678.4 (n=3) | mediana 3.98, média 3.96, desvio 0.03, p95 3.98 (n=3) | mediana 3.88, média 3.89, desvio 0.03, p95 3.91 (n=3) | 4 / 3.99 | 0 / 0 | 100.0% mín., 100.0% média |

## Recuperação após prazo estourado

| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |
|---|---:|---|---|---|
| K=8 N=8 no-flaky | 0 | - | - | - |
| K=2 N=8 no-flaky | 0 | - | - | - |
| K=1 N=8 no-flaky | 0 | - | - | - |
| K=4 N=8 no-flaky | 0 | - | - | - |

## Speedup por K

| N | Contador lento | K | Amostras | Parede mediana (ms) | Parede p95 (ms) | Speedup | Rodada 1 mediana (ms) | Speedup da rodada 1 | Ideal | Paralelismo (mapa) mediano |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | não | 1 | 3 | 2568.5 | 2568.9 | 1.00 | 2539.4 | 1.00 | 1.00 | 0.98 |
| 8 | não | 2 | 3 | 1293.7 | 1295.0 | 1.99 | 1266.0 | 2.01 | 2.00 | 1.97 |
| 8 | não | 4 | 3 | 668.6 | 678.4 | 3.84 | 643.5 | 3.95 | 4.00 | 3.98 |
| 8 | não | 8 | 3 | 351.5 | 368.4 | 7.31 | 327.4 | 7.76 | 8.00 | 7.88 |

## Amostras

| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| K=8 N=8 no-flaky | 1 | COMPLETED | 368.4 | 340.4 | 7.94 | 8 | 0 | 61 / 61 | 0 |
| K=8 N=8 no-flaky | 2 | COMPLETED | 346.0 | 323.7 | 7.88 | 8 | 0 | 61 / 61 | 0 |
| K=8 N=8 no-flaky | 3 | COMPLETED | 351.5 | 327.4 | 7.83 | 8 | 0 | 61 / 61 | 0 |
| K=2 N=8 no-flaky | 1 | COMPLETED | 1290.1 | 1264.1 | 1.97 | 2 | 0 | 61 / 61 | 0 |
| K=2 N=8 no-flaky | 2 | COMPLETED | 1293.7 | 1266.0 | 1.97 | 2 | 0 | 61 / 61 | 0 |
| K=2 N=8 no-flaky | 3 | COMPLETED | 1295.0 | 1270.3 | 1.97 | 2 | 0 | 61 / 61 | 0 |
| K=1 N=8 no-flaky | 1 | COMPLETED | 2568.5 | 2539.4 | 0.98 | 1 | 0 | 61 / 61 | 0 |
| K=1 N=8 no-flaky | 2 | COMPLETED | 2568.9 | 2543.8 | 0.98 | 1 | 0 | 61 / 61 | 0 |
| K=1 N=8 no-flaky | 3 | COMPLETED | 2532.7 | 2509.5 | 0.98 | 1 | 0 | 61 / 61 | 0 |
| K=4 N=8 no-flaky | 1 | COMPLETED | 678.4 | 649.6 | 3.98 | 4 | 0 | 61 / 61 | 0 |
| K=4 N=8 no-flaky | 2 | COMPLETED | 657.6 | 633.1 | 3.98 | 4 | 0 | 61 / 61 | 0 |
| K=4 N=8 no-flaky | 3 | COMPLETED | 668.6 | 643.5 | 3.93 | 4 | 0 | 61 / 61 | 0 |

Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida pelo intervalo entre o primeiro início e o último término; recuperação = `TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); completude = eventos esperados presentes / esperados.
