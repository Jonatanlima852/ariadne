# Resultados de 29 de outubro de 2026

Coleta local, sem LLM e sem Docker: Apple M3 Pro (11 núcleos), macOS 27.0.1,
Go 1.26.3, Python 3.14.4, código em `5d693ff` (branch `phase-v2`), binários
compilados de `runtime/` para `.ariadne/bin`. Cada diretório guarda a
análise (`report.json`, `report.md`, figuras) e, por execução, o
`events.jsonl` do orquestrador, o `manifest.json` e o `summary.json`. Os
`results.jsonl`/`mission-result.json` (centenas de KB por amostra, por causa
dos textos dos fragmentos) não foram preservados; `report.json` contém os
intervalos por passo e as tentativas usados nas figuras.

| Coleta | Comando | Conteúdo |
|---|---|---|
| `main/` | `FANOUT_WORKERS=4 FANOUT_SHARDS=8 FANOUT_FLAKY=1 ./ariadne run studies/scenarios/fanout/scenario.py --repeat 5` | K=4, N=8, contador lento, 5 amostras; Gantt de cada amostra |
| `sweep/` | `python -m studies.scenarios.fanout.campaign --workers 1 2 4 8 --repeat 3 --flaky 0` | speedup por K sem o contador lento; Gantt da primeira amostra de cada K |
| `sweep-flaky/` | `python -m studies.scenarios.fanout.campaign --workers 1 2 4 --repeat 1 --flaky 1` | K em {1, 2, 4} com o contador lento, uma amostra cada |

Análises geradas com `python -m studies.scenarios.fanout.analysis <runs> --output <analysis>`
(PNG via `uv run --with matplotlib`).

## Números principais

Varredura sem o contador lento (3 amostras por K, N=8, 300 ms por fragmento):

| K | Parede mediana (ms) | p95 (ms) | Speedup | Ideal | Fator de paralelismo (mapa) | Concorrência pico |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2550,6 | 2557,9 | 1,00 | 1 | 0,98 | 1 |
| 2 | 1294,2 | 1302,3 | 1,97 | 2 | 1,96 | 2 |
| 4 | 666,8 | 670,9 | 3,82 | 4 | 3,94 | 4 |
| 8 | 362,5 | 373,2 | 7,04 | 8 | 7,94 | 8 |

K=4, N=8 com o contador lento, 5 amostras: 5/5 completas; 8 prazos
estourados e 8 reatribuições (duas amostras com uma, três com duas, conforme
o rodízio entregou um ou dois passos ao `counter-flaky`); detecção do prazo
mediana 1501,4 ms (prazo configurado 1500 ms); recuperação
`TASK_REASSIGNED - TASK_TIMEOUT` mediana 1,74 ms, média 2,28 ms, desvio 1,47 ms,
p95 4,83 ms; conclusão após o timeout mediana 313,4 ms; tempo de parede
mediana 3661,2 ms (média 3079,4 ms, p95 3687,3 ms); concorrência de mapa pico
4; completude do rastro 100% (63 a 65 eventos esperados por missão, todos
presentes).

Varredura com o contador lento (1 amostra por K): parede 8563,0 ms (K=1, 4
reatribuições), 4303,5 ms (K=2, 2 reatribuições), 2176,3 ms (K=4, 1
reatribuição); speedup 1,99 e 3,93.
