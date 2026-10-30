# Estudo de paralelismo e reatribuição: relatório

## Execuções analisadas

| Execução | Grupo | Amostras |
|---|---|---:|
| `ariadne-b411a38300724a8c972b2d7fa97dc7ac` | K=4 N=8 flaky | 1 |
| `ariadne-ce6d072ba53149e192bda145208df200` | K=1 N=8 flaky | 1 |
| `ariadne-ed72a6e13a0647dabc2371d58e2aac9d` | K=2 N=8 flaky | 1 |

## Por grupo (K trabalhadores, N fragmentos, contador lento)

| Grupo | Amostras completas | Tempo de parede (ms) | Fator de paralelismo (mapa) | Fator (rodada 1, todos os passos) | Concorrência de mapa (pico / média) | Reatribuições (eventos / passos) | Completude do rastro |
|---|---:|---|---|---|---|---:|---:|
| K=4 N=8 flaky | 1/1 | mediana 2176.3, média 2176.3, desvio 0.0, p95 2176.3 (n=1) | mediana 1.15, média 1.15, desvio 0.00, p95 1.15 (n=1) | mediana 1.15, média 1.15, desvio 0.00, p95 1.15 (n=1) | 4 / 1.87 | 1 / 1 | 100.0% mín., 100.0% média |
| K=1 N=8 flaky | 1/1 | mediana 8563.0, média 8563.0, desvio 0.0, p95 8563.0 (n=1) | mediana 0.29, média 0.29, desvio 0.00, p95 0.29 (n=1) | mediana 0.29, média 0.29, desvio 0.00, p95 0.29 (n=1) | 1 / 1.00 | 4 / 4 | 100.0% mín., 100.0% média |
| K=2 N=8 flaky | 1/1 | mediana 4303.5, média 4303.5, desvio 0.0, p95 4303.5 (n=1) | mediana 0.57, média 0.57, desvio 0.00, p95 0.57 (n=1) | mediana 0.57, média 0.57, desvio 0.00, p95 0.57 (n=1) | 2 / 1.29 | 2 / 2 | 100.0% mín., 100.0% média |

## Recuperação após prazo estourado

| Grupo | Passos com timeout | Detecção do prazo (ms) | Recuperação TASK_REASSIGNED - TASK_TIMEOUT (ms) | Conclusão após o timeout (ms) |
|---|---:|---|---|---|
| K=4 N=8 flaky | 1 | mediana 1501.2, média 1501.2, desvio 0.0, p95 1501.2 (n=1) | mediana 1.19, média 1.19, desvio 0.00, p95 1.19 (n=1) | mediana 310.5, média 310.5, desvio 0.0, p95 310.5 (n=1) |
| K=1 N=8 flaky | 4 | mediana 1501.9, média 1502.3, desvio 1.2, p95 1504.1 (n=4) | mediana 2.30, média 2.45, desvio 1.06, p95 3.74 (n=4) | mediana 310.4, média 310.9, desvio 1.9, p95 313.5 (n=4) |
| K=2 N=8 flaky | 2 | mediana 1501.2, média 1501.2, desvio 0.7, p95 1501.7 (n=2) | mediana 3.33, média 3.33, desvio 3.77, p95 5.99 (n=2) | mediana 313.3, média 313.3, desvio 6.3, p95 317.8 (n=2) |

| Grupo | Amostra | Passo | Primeiro agente | Agente final | Tentativas |
|---|---:|---|---|---|---:|
| K=4 N=8 flaky | 1 | map-8 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-2 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-4 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-6 | counter-flaky | counter-1 | 2 |
| K=1 N=8 flaky | 1 | map-8 | counter-flaky | counter-1 | 2 |
| K=2 N=8 flaky | 1 | map-4 | counter-flaky | counter-1 | 2 |
| K=2 N=8 flaky | 1 | map-5 | counter-flaky | counter-2 | 2 |

## Speedup por K

| N | Contador lento | K | Amostras | Parede mediana (ms) | Parede p95 (ms) | Speedup | Rodada 1 mediana (ms) | Speedup da rodada 1 | Ideal | Paralelismo (mapa) mediano |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | sim | 1 | 1 | 8563.0 | 8563.0 | 1.00 | 8536.0 | 1.00 | 1.00 | 0.29 |
| 8 | sim | 2 | 1 | 4303.5 | 4303.5 | 1.99 | 4276.2 | 2.00 | 2.00 | 0.57 |
| 8 | sim | 4 | 1 | 2176.3 | 2176.3 | 3.93 | 2150.5 | 3.97 | 4.00 | 1.15 |

## Amostras

| Grupo | Amostra | Estado | Parede (ms) | Rodada 1 (ms) | Paralelismo (mapa) | Concorrência pico | Reatribuições | Eventos esperados / presentes | Faltantes |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| K=4 N=8 flaky | 1 | COMPLETED | 2176.3 | 2150.5 | 1.15 | 4 | 1 | 63 / 63 | 0 |
| K=1 N=8 flaky | 1 | COMPLETED | 8563.0 | 8536.0 | 0.29 | 1 | 4 | 69 / 69 | 0 |
| K=2 N=8 flaky | 1 | COMPLETED | 4303.5 | 4276.2 | 0.57 | 2 | 2 | 65 / 65 | 0 |

Definições: tempo de parede = `completed_at - created_at` do `MissionResult`; fator de paralelismo = soma das durações dos passos (`started_at`/`completed_at` do `TaskResult`) dividida pelo intervalo entre o primeiro início e o último término; recuperação = `TASK_REASSIGNED - TASK_TIMEOUT` no `events.jsonl`; concorrência = tentativas de mapa em execução ao mesmo tempo segundo `TASK_ASSIGNED`/`TASK_REASSIGNED` e seus términos (inclui a tentativa que estourou o prazo); completude = eventos esperados presentes / esperados.
