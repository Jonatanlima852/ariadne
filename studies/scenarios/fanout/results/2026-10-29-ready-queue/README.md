# Resultados de 29 de outubro de 2026, engine com fila de prontos

Mesma máquina, mesmos comandos e mesmos parâmetros da coleta anterior em
[`../2026-10-29`](../2026-10-29/README.md), repetidos depois de três mudanças no
runtime (commits `a832b44`, `32f5e8a`, `365ffa5`): o engine de workflow passou
de ondas com barreira para fila de prontos; o plano do planejador passou a
carregar `deadline_ms`, `retry_policy` e `selection_policy` por passo (o
fan-out deixou de usar a variável `EXECUTION_TIMEOUT`); e `TaskResult`
passou a registrar todas as tentativas e a família do agente. Cada diretório
guarda a análise e, por execução, `events.jsonl`, `manifest.json` e
`summary.json`.

## Antes e depois, K=4, N=8, contador lento, 5 amostras

| Métrica | Ondas com barreira (antes) | Fila de prontos (depois) |
|---|---:|---:|
| Tempo de parede mediano | 3.661,2 ms | 2.166,0 ms |
| Tempo de parede médio (desvio) | 3.079,4 ms (819,8) | 2.169,4 ms (218,0) |
| Tempo de parede p95 | 3.687,3 ms | 2.477,6 ms |
| Fator de paralelismo (mapa), mediana | 0,67 | 1,16 |
| Concorrência de mapa, média | 1,51 | 2,25 |
| Reatribuições (eventos / passos) | 8 / 8 | 8 / 8 |
| Recuperação `TASK_REASSIGNED - TASK_TIMEOUT`, mediana (p95) | 1,74 ms (4,83) | 2,02 ms (2,62) |
| Conclusão após o timeout, mediana | 313,4 ms | 312,9 ms |
| Completude do rastro | 100% | 100% |

No Gantt (`main/analysis/gantt-k4-n8-flaky-s1.png`) os três contadores
saudáveis recebem a segunda leva de mapas assim que terminam a primeira,
enquanto o `counter-flaky` ainda segura `map-5`; antes, eles esperavam o
prazo estourar. O tempo de parede passa a ser dominado pelo próprio prazo do
passo (1.500 ms) mais a repetição (cerca de 300 ms), que é o mínimo possível
sem cancelar a tentativa lenta mais cedo.

## Varredura com o contador lento, uma amostra por K

| K | Parede antes (ms) | Parede depois (ms) | Speedup depois |
|---:|---:|---:|---:|
| 1 | 8.563,0 | 8.585,7 | 1,00 |
| 2 | 4.303,5 | 2.812,3 | 3,05 |
| 4 | 2.176,3 | 2.187,0 | 3,93 |

Com K=1 nada muda (não há com quem paralelizar). Com K=2 o ganho é maior que
o ideal porque a referência K=1 inclui quatro timeouts em série. Com K=4 a
amostra anterior já tinha o passo lento na última leva, por isso os dois
valores coincidem; a diferença aparece na mediana de cinco amostras acima.

## Varredura sem o contador lento, 3 amostras por K

| K | Parede mediana (ms) | p95 (ms) | Speedup | Ideal | Fator de paralelismo (mapa) |
|---:|---:|---:|---:|---:|---:|
| 1 | 2.568,5 | 2.568,9 | 1,00 | 1 | 0,98 |
| 2 | 1.293,7 | 1.295,0 | 1,99 | 2 | 1,97 |
| 4 | 668,6 | 678,4 | 3,84 | 4 | 3,98 |
| 8 | 351,5 | 368,4 | 7,31 | 8 | 7,88 |

Sem falhas o escalonador novo e o antigo coincidem, como esperado: a
diferença entre eles só aparece quando um passo demora mais que os outros.
