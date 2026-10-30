# Estudo de paralelismo e reatribuição: relatório

## Execuções analisadas

| Execução | Grupo | Amostras |
|---|---|---:|
| `ariadne-45d77287d7fa410a990d8a1ce9226f1f` | K=4 N=8 flaky | 5 |

## Por grupo (K trabalhadores, N fragmentos, contador lento)

| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |
|---|---:|---|---|---|---|---:|---:|
| K=4 N=8 flaky | 5/5 | mediana 3661.2, média 3079.4, desvio 819.8, p95 3687.3 (n=5) | mediana 0.67, média 0.86, desvio 0.26, p95 1.15 (n=5) | mediana 0.67, média 0.86, desvio 0.26, p95 1.15 (n=5) | 4 / 1.51 | 8 / 8 | 100.0% mín., 100.0% média |

## Recuperação após prazo estourado

| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |
|---|---:|---|---|---|
| K=4 N=8 flaky | 8 | mediana 1501.4, média 1501.5, desvio 0.3, p95 1502.0 (n=8) | mediana 1.74, média 2.28, desvio 1.47, p95 4.83 (n=8) | mediana 313.4, média 314.8, desvio 7.1, p95 329.5 (n=8) |

| Grupo | Amostra | Passo | Primeiro agente | Agente final | Tentativas |
|---|---:|---|---|---|---:|
| K=4 N=8 flaky | 1 | map-8 | counter-flaky | counter-1 | 2 |
| K=4 N=8 flaky | 2 | map-2 | counter-flaky | counter-2 | 2 |
| K=4 N=8 flaky | 2 | map-5 | counter-flaky | counter-3 | 2 |
| K=4 N=8 flaky | 3 | map-4 | counter-flaky | counter-4 | 2 |
| K=4 N=8 flaky | 4 | map-2 | counter-flaky | counter-1 | 2 |
| K=4 N=8 flaky | 4 | map-8 | counter-flaky | counter-2 | 2 |
| K=4 N=8 flaky | 5 | map-4 | counter-flaky | counter-3 | 2 |
| K=4 N=8 flaky | 5 | map-6 | counter-flaky | counter-4 | 2 |

## Amostras

| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| K=4 N=8 flaky | 1 | COMPLETED | 2168.7 | 2142.7 | 1.15 | 4 | 1 | 63 / 63 | 0 |
| K=4 N=8 flaky | 2 | COMPLETED | 3685.7 | 3660.7 | 0.67 | 4 | 2 | 65 / 65 | 0 |
| K=4 N=8 flaky | 3 | COMPLETED | 2194.3 | 2168.5 | 1.14 | 4 | 1 | 63 / 63 | 0 |
| K=4 N=8 flaky | 4 | COMPLETED | 3661.2 | 3638.1 | 0.67 | 4 | 2 | 65 / 65 | 0 |
| K=4 N=8 flaky | 5 | COMPLETED | 3687.3 | 3656.8 | 0.67 | 4 | 2 | 65 / 65 | 0 |

Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida pelo intervalo entre o primeiro início e o último término; recuperação = `TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); completude = eventos esperados presentes / esperados.
