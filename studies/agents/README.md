# Agentes compartilhados

`text.py` oferece fábricas `echo_agent` e `uppercase_agent`, usadas por tarefa
simples, workflow e recuperação. Cada cenário instancia os participantes e
configura nomes e atrasos; não copia a implementação do comportamento.

As pastas `echo-agent`, `mock-agent`, `failing-agent`, `bdi-agent`, `llm-agent`
e `meeting-scheduler` contêm agentes executáveis, incluindo suporte Docker e
implementações históricas. Os adaptadores BDI e LLM históricos também expõem
capacidades logísticas implementadas no cenário de logística.

Agentes usados exclusivamente por um cenário ficam no próprio cenário. Os
primitivos genéricos (`Agent`, `BdiAgent`, `LlmAgent`) pertencem ao SDK.

[Estudos](../README.md)
