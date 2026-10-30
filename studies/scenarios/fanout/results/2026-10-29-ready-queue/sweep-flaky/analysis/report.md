# Estudo de paralelismo e reatribuição: relatório

## Execuções analisadas

| Execução | Grupo | Amostras |
|---|---|---:|
| `ariadne-0c966aea64dd491890d0bbe1456ec51a` | K=4 N=8 flaky | 1 |
| `ariadne-516b483ab3c5428885bfb76fc0e6cb1c` | K=1 N=8 flaky | 1 |
| `ariadne-6f32236f574a4e4898df05ee4ebfa256` | K=2 N=8 flaky | 1 |

## Por grupo (K trabalhadores, N fragmentos, contador lento)

| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |
|---|---:|---|---|---|---|---:|---:|
| K=4 N=8 flaky | 1/1 | mediana 2187.0, média 2187.0, desvio 0.0, p95 2187.0 (n=1) | mediana 1.16, média 1.16, desvio 0.00, p95 1.16 (n=1) | mediana 1.15, média 1.15, desvio 0.00, p95 1.15 (n=1) | 4 / 1.88 | 1 / 1 | 100.0% mín., 100.0% média |
| K=1 N=8 flaky | 1/1 | mediana 8585.7, média 8585.7, desvio 0.0, p95 8585.7 (n=1) | mediana 0.29, média 0.29, desvio 0.00, p95 0.29 (n=1) | mediana 0.29, média 0.29, desvio 0.00, p95 0.29 (n=1) | 1 / 1.00 | 4 / 4 | 100.0% mín., 100.0% média |
| K=2 N=8 flaky | 1/1 | mediana 2812.3, média 2812.3, desvio 0.0, p95 2812.3 (n=1) | mediana 0.90, média 0.90, desvio 0.00, p95 0.90 (n=1) | mediana 0.89, média 0.89, desvio 0.00, p95 0.89 (n=1) | 2 / 1.99 | 2 / 2 | 100.0% mín., 100.0% média |

## Recuperação após prazo estourado

| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |
|---|---:|---|---|---|
| K=4 N=8 flaky | 1 | mediana 1502.6, média 1502.6, desvio 0.0, p95 1502.6 (n=1) | mediana 2.55, média 2.55, desvio 0.00, p95 2.55 (n=1) | mediana 315.3, média 315.3, desvio 0.0, p95 315.3 (n=1) |
| K=1 N=8 flaky | 4 | mediana 1502.1, média 1502.0, desvio 0.6, p95 1502.7 (n=4) | mediana 1.94, média 1.98, desvio 0.60, p95 2.71 (n=4) | mediana 316.7, média 316.7, desvio 2.2, p95 319.2 (n=4) |
| K=2 N=8 flaky | 2 | mediana 1501.8, média 1501.8, desvio 0.9, p95 1502.4 (n=2) | mediana 1.48, média 1.48, desvio 0.07, p95 1.53 (n=2) | mediana 310.6, média 310.6, desvio 3.4, p95 313.0 (n=2) |

| Grupo | Amostra | Passo | Primeiro agente | Agente final | Tentativas |
|---|---:|---|---|---|---:|
| K=4 N=8 flaky | 1 | map-6 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-2 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-4 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-6 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-8 | counter-flaky | counter-1 | 2 |
| K=2 N=8 flaky | 1 | map-3 | counter-flaky | counter-1 | 2 |
| K=2 N=8 flaky | 1 | map-6 | counter-flaky | counter-2 | 2 |

## Speedup por K

| N | Contador lento | K | Amostras | Parede mediana (ms) | Parede p95 (ms) | Speedup | Rodada 1 mediana (ms) | Speedup da rodada 1 | Ideal | Paralelismo (mapa) mediano |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | sim | 1 | 1 | 8585.7 | 8585.7 | 1.00 | 8558.0 | 1.00 | 1.00 | 0.29 |
| 8 | sim | 2 | 1 | 2812.3 | 2812.3 | 3.05 | 2785.7 | 3.07 | 2.00 | 0.90 |
| 8 | sim | 4 | 1 | 2187.0 | 2187.0 | 3.93 | 2158.1 | 3.97 | 4.00 | 1.16 |

## Amostras

| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| K=4 N=8 flaky | 1 | COMPLETED | 2187.0 | 2158.1 | 1.16 | 4 | 1 | 63 / 63 | 0 |
| K=1 N=8 flaky | 1 | COMPLETED | 8585.7 | 8558.0 | 0.29 | 1 | 4 | 69 / 69 | 0 |
| K=2 N=8 flaky | 1 | COMPLETED | 2812.3 | 2785.7 | 0.90 | 2 | 2 | 65 / 65 | 0 |

Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida pelo intervalo entre o primeiro início e o último término; recuperação = `TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); completude = eventos esperados presentes / esperados.
