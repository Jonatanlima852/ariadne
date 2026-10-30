# Estudo de paralelismo e reatribuição: relatório

## Execuções analisadas

| Execução | Grupo | Amostras |
|---|---|---:|
| `ariadne-a3592c781c94483aa758b9eb4882edc1` | K=4 N=8 flaky | 5 |

## Por grupo (K trabalhadores, N fragmentos, contador lento)

| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |
|---|---:|---|---|---|---|---:|---:|
| K=4 N=8 flaky | 5/5 | mediana 2166.0, média 2169.4, desvio 218.0, p95 2477.6 (n=5) | mediana 1.16, média 1.17, desvio 0.12, p95 1.35 (n=5) | mediana 1.15, média 1.16, desvio 0.12, p95 1.35 (n=5) | 4 / 2.25 | 8 / 8 | 100.0% mín., 100.0% média |

## Recuperação após prazo estourado

| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |
|---|---:|---|---|---|
| K=4 N=8 flaky | 8 | mediana 1502.4, média 1502.1, desvio 0.7, p95 1502.7 (n=8) | mediana 2.02, média 1.99, desvio 0.52, p95 2.62 (n=8) | mediana 312.9, média 313.2, desvio 3.3, p95 319.2 (n=8) |

| Grupo | Amostra | Passo | Primeiro agente | Agente final | Tentativas |
|---|---:|---|---|---|---:|
| K=4 N=8 flaky | 1 | map-5 | counter-flaky | counter-1 | 2 |
| K=4 N=8 flaky | 2 | map-2 | counter-flaky | counter-2 | 2 |
| K=4 N=8 flaky | 2 | map-7 | counter-flaky | counter-3 | 2 |
| K=4 N=8 flaky | 3 | map-1 | counter-flaky | counter-4 | 2 |
| K=4 N=8 flaky | 4 | map-4 | counter-flaky | counter-1 | 2 |
| K=4 N=8 flaky | 4 | map-6 | counter-flaky | counter-2 | 2 |
| K=4 N=8 flaky | 5 | map-2 | counter-flaky | counter-3 | 2 |
| K=4 N=8 flaky | 5 | map-8 | counter-flaky | counter-4 | 2 |

## Amostras

| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| K=4 N=8 flaky | 1 | COMPLETED | 2183.9 | 2156.1 | 1.15 | 4 | 1 | 63 / 63 | 0 |
| K=4 N=8 flaky | 2 | COMPLETED | 2166.0 | 2138.7 | 1.16 | 4 | 2 | 65 / 65 | 0 |
| K=4 N=8 flaky | 3 | COMPLETED | 1861.6 | 1832.9 | 1.35 | 4 | 1 | 63 / 63 | 0 |
| K=4 N=8 flaky | 4 | COMPLETED | 2158.1 | 2135.4 | 1.16 | 4 | 2 | 65 / 65 | 0 |
| K=4 N=8 flaky | 5 | COMPLETED | 2477.6 | 2453.6 | 1.01 | 4 | 2 | 65 / 65 | 0 |

Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida pelo intervalo entre o primeiro início e o último término; recuperação = `TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); completude = eventos esperados presentes / esperados.
