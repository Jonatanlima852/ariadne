# Resultados preservados da v3

## 2026-10-30: suítes básica e de estresse, uma observação por caso

Primeira coleta real da v3: dez casos da suíte básica e dez da suíte de
estresse, cada um nas duas configurações, `gpt-5.6-luna`, uma observação por
combinação (40 missões). Executada por `./ariadne campaign` sobre
`v3/campaign.py`, com cada observação em contêineres próprios (contrato
2.0.0, fila de prontos, três entregadores BDI em paralelo). Máquina: Apple M3
Pro, macOS 27, Docker Desktop 28.4; código na `main` entre `0647e03` e `4f35d03`.

| Suíte | Ariadne v3 | Single LLM v3 |
|---|---|---|
| basic | 18/20 · 18 no prazo · 12 s · 43 mil tokens | 18/20 · 18 no prazo · 12 s · 31 mil tokens (n=10) |
| stress | 73/76 · 63 no prazo · 70 s · 183 mil tokens | 63/76 · 54 no prazo · 129 s · 209 mil tokens (n=9) |

Tempo é a média das missões concluídas (`created_at` a `completed_at` do
`MissionResult`, contêineres já no ar). Na suíte de estresse o Single LLM
teve uma missão sem resultado (s01: timeout de 90 s do provedor na chamada
do planejador); ela conta como 0/8 entregues e fica sem tokens. Nos nove
pares com uso conhecido dos dois lados, o Ariadne usou
167 mil tokens contra
209 mil.

Cada pasta `campaign-*/runs/ariadne-*/` guarda `manifest.json`,
`summary.json`, `mission-result.json` e `events.jsonl` da observação; os
logs dos contêineres não foram preservados. `analysis/` tem a saída de
`python -m studies.scenarios.logistics.v3.analysis` sobre as pastas da suíte
(`results.json`, `comparison.md`, CSVs, `analysis.md`).

A coleta foi feita em mais de uma campanha porque duas falhas do executor,
corrigidas no mesmo dia, invalidaram observações: o limite de 60 s do RPC
da campanha (`980c809`) e o limite de 4 MB de mensagem gRPC no resultado
de s08 (`4f35d03`). As observações invalidadas foram repetidas e só as
válidas estão aqui; as quatro da suíte básica quebradas por uma edição
concorrente no código também foram repetidas.

[Estudo v3](../README.md)
