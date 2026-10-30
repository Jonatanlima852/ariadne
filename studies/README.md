# Estudos por cenário

Cada pasta em `scenarios/` representa um assunto estudado no TG. Dentro dela
ficam os agentes, domínio, regras, casos, benchmarks e métricas necessários.
A arquitetura do agente (BDI ou LLM) e o modo de execução não definem cenários separados.

| Cenário | O que investigar |
|---|---|
| [Tarefa simples](scenarios/basic_task/README.md) | Descoberta, atribuição e resposta |
| [Seleção de agentes](scenarios/agent_selection/README.md) | Políticas e distribuição de tarefas |
| [Workflow sequencial](scenarios/sequential_workflow/README.md) | Dependências e passagem de resultados |
| [Recuperação](scenarios/failure_reassignment/README.md) | Prazo e nova atribuição |
| [Mensageria](scenarios/messaging/README.md) | Envelopes, entrega e correlação |
| [Saudação](scenarios/greeting/README.md) | Resposta estruturada de um provedor LLM |
| [Agendamento](scenarios/meeting/README.md) | Crenças, restrições e planos |
| [Rotas](scenarios/routing/README.md) | Missão didática: planejador LLM → BDI deliberativo → explicação LLM |
| [Logística](scenarios/logistics/README.md) | Missões com energia, prazo e restrições; LLM-only e híbrido |
| [Fan-out](scenarios/fanout/README.md) | Paralelismo de passos, reatribuição após prazo e completude do rastro; determinístico, sem LLM |

## Estrutura de um cenário

```text
scenarios/<assunto>/
  README.md          # pergunta estudada e como executar
  scenario.py        # entrada única: agentes e tarefa ou missão
  agents/            # agentes deste cenário, quando houver
  runs/              # execuções locais (ignorado pelo git)
  campaigns/         # campanhas locais (ignorado pelo git)
  campaign.py        # opcional: matriz e repetições para ./ariadne campaign
  analysis.py        # opcional: análise das evidências, python -m studies.scenarios.<assunto>.analysis
```

Crie apenas as pastas necessárias. Arquivos de domínio, regras e dados ficam
junto ao cenário. Toda entrada é uma declaração `Scenario` executada por
`./ariadne run`, que sobe os agentes em contêineres; não há topologias
escritas à mão nem Dockerfiles por agente.

Os agentes pertencem ao cenário que define seu comportamento. Mecanismos genéricos
ficam no SDK; a extração compartilhada de métricas de eventos fica em
[tools/runtime_metrics](../tools/runtime_metrics/README.md).
Não há diretório global de agentes nem cenário agregador de benchmarks.

A seleção BDI isolada é uma [fixture funcional do SDK](../sdk/python/tests/fixtures/route_choice.py),
não um estudo comparativo separado. A antiga suíte A–D em Docker foi removida;
os rótulos permanecem apenas em evidências históricas.
Evidências históricas mantêm os bytes e caminhos registrados na coleta.

[Guia de execução](../docs/quickstart.md) · [Avaliação](../docs/evaluation.md)
