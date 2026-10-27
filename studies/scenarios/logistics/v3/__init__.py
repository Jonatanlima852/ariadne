"""Logística v3: o estudo logístico executado como missão no laço do orquestrador Go.

Duas configurações compartilham runtime, evidências e visualizador:
``ariadne-v3`` (planejador LLM + agentes BDI deliberativos + executor
determinístico) e ``single-llm-v3`` (o Single LLM da v2 embrulhado como
planejador de missão). O domínio (estado, transições, incidentes, métricas) é
importado da v2 sem alteração.
"""
