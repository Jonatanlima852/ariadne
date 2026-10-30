# Estudo de paralelismo e reatribuição: relatório

## Execuções analisadas

| Execução | Grupo | Amostras |
|---|---|---:|
| `ariadne-5744c74583784bf8a430be5370ec391f` | K=1 N=8 no-flaky | 3 |
| `ariadne-8816a1d3f31e4dd19a92008ad2d00e3e` | K=4 N=8 no-flaky | 3 |
| `ariadne-b8ceffd13f6246f5b848b446ce0aa622` | K=2 N=8 no-flaky | 3 |
| `ariadne-d9dc9cadd6e748509e4477b53cc75b31` | K=8 N=8 no-flaky | 3 |

## Por grupo (K trabalhadores, N fragmentos, contador lento)

| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |
|---|---:|---|---|---|---|---:|---:|
| K=1 N=8 no-flaky | 3/3 | mediana 2550.6, média 2544.9, desvio 16.7, p95 2557.9 (n=3) | mediana 0.98, média 0.98, desvio 0.00, p95 0.98 (n=3) | mediana 0.98, média 0.98, desvio 0.00, p95 0.98 (n=3) | 1 / 0.99 | 0 / 0 | 100.0% mín., 100.0% média |
| K=4 N=8 no-flaky | 3/3 | mediana 666.8, média 666.0, desvio 5.4, p95 670.9 (n=3) | mediana 3.94, média 3.94, desvio 0.02, p95 3.96 (n=3) | mediana 3.87, média 3.87, desvio 0.02, p95 3.88 (n=3) | 4 / 3.97 | 0 / 0 | 100.0% mín., 100.0% média |
| K=2 N=8 no-flaky | 3/3 | mediana 1294.2, média 1296.8, desvio 4.7, p95 1302.3 (n=3) | mediana 1.96, média 1.96, desvio 0.01, p95 1.98 (n=3) | mediana 1.94, média 1.94, desvio 0.01, p95 1.95 (n=3) | 2 / 1.99 | 0 / 0 | 100.0% mín., 100.0% média |
| K=8 N=8 no-flaky | 3/3 | mediana 362.5, média 365.5, desvio 6.7, p95 373.2 (n=3) | mediana 7.94, média 7.93, desvio 0.02, p95 7.94 (n=3) | mediana 7.50, média 7.49, desvio 0.01, p95 7.51 (n=3) | 8 / 7.93 | 0 / 0 | 100.0% mín., 100.0% média |

## Recuperação após prazo estourado

| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |
|---|---:|---|---|---|
| K=1 N=8 no-flaky | 0 | - | - | - |
| K=4 N=8 no-flaky | 0 | - | - | - |
| K=2 N=8 no-flaky | 0 | - | - | - |
| K=8 N=8 no-flaky | 0 | - | - | - |

## Speedup por K

| N | Contador lento | K | Amostras | Parede mediana (ms) | Parede p95 (ms) | Speedup | Rodada 1 mediana (ms) | Speedup da rodada 1 | Ideal | Paralelismo (mapa) mediano |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | não | 1 | 3 | 2550.6 | 2557.9 | 1.00 | 2521.7 | 1.00 | 1.00 | 0.98 |
| 8 | não | 2 | 3 | 1294.2 | 1302.3 | 1.97 | 1270.0 | 1.99 | 2.00 | 1.96 |
| 8 | não | 4 | 3 | 666.8 | 670.9 | 3.82 | 643.3 | 3.92 | 4.00 | 3.94 |
| 8 | não | 8 | 3 | 362.5 | 373.2 | 7.04 | 338.1 | 7.46 | 8.00 | 7.94 |

## Amostras

| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| K=1 N=8 no-flaky | 1 | COMPLETED | 2550.6 | 2521.7 | 0.98 | 1 | 0 | 61 / 61 | 0 |
| K=1 N=8 no-flaky | 2 | COMPLETED | 2557.9 | 2531.6 | 0.98 | 1 | 0 | 61 / 61 | 0 |
| K=1 N=8 no-flaky | 3 | COMPLETED | 2526.1 | 2503.2 | 0.98 | 1 | 0 | 61 / 61 | 0 |
| K=4 N=8 no-flaky | 1 | COMPLETED | 670.9 | 644.5 | 3.96 | 4 | 0 | 61 / 61 | 0 |
| K=4 N=8 no-flaky | 2 | COMPLETED | 660.1 | 636.6 | 3.92 | 4 | 0 | 61 / 61 | 0 |
| K=4 N=8 no-flaky | 3 | COMPLETED | 666.8 | 643.3 | 3.94 | 4 | 0 | 61 / 61 | 0 |
| K=2 N=8 no-flaky | 1 | COMPLETED | 1302.3 | 1276.3 | 1.96 | 2 | 0 | 61 / 61 | 0 |
| K=2 N=8 no-flaky | 2 | COMPLETED | 1294.2 | 1267.5 | 1.98 | 2 | 0 | 61 / 61 | 0 |
| K=2 N=8 no-flaky | 3 | COMPLETED | 1293.9 | 1270.0 | 1.96 | 2 | 0 | 61 / 61 | 0 |
| K=8 N=8 no-flaky | 1 | COMPLETED | 373.2 | 346.4 | 7.91 | 8 | 0 | 61 / 61 | 0 |
| K=8 N=8 no-flaky | 2 | COMPLETED | 360.9 | 336.2 | 7.94 | 8 | 0 | 61 / 61 | 0 |
| K=8 N=8 no-flaky | 3 | COMPLETED | 362.5 | 338.1 | 7.94 | 8 | 0 | 61 / 61 | 0 |

Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida pelo intervalo entre o primeiro início e o último término; recuperação = `TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); completude = eventos esperados presentes / esperados.
