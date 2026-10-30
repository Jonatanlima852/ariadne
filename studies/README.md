# Estudos por cenário

Cada pasta em `scenarios/` representa um assunto estudado no TG. Dentro dela
ficam os agentes, domínio, regras, casos, benchmarks e métricas necessários.
A arquitetura do agente (BDI ou LLM) e o modo de execução não definem cenários separados.

| Cenário | O que investigar |
|---|---|
| [Tarefa simples](scenarios/basic_task/README.md) | Descoberta, atribuição e resposta; benchmark A |
| [Seleção de agentes](scenarios/agent_selection/README.md) | Políticas e distribuição de tarefas; benchmark B |
| [Workflow sequencial](scenarios/sequential_workflow/README.md) | Dependências e passagem de resultados |
| [Recuperação](scenarios/failure_reassignment/README.md) | Prazo e nova atribuição; benchmark D |
| [Mensageria](scenarios/messaging/README.md) | Envelopes, entrega e correlação |
| [Saudação](scenarios/greeting/README.md) | Resposta estruturada de um provedor LLM |
| [Agendamento](scenarios/meeting/README.md) | Crenças, restrições e planos |
| [Rotas](scenarios/routing/README.md) | Missão didática: planejador LLM → BDI deliberativo → explicação LLM; benchmark C |
| [Logística](scenarios/logistics/README.md) | Missões com energia, prazo e restrições; LLM-only e híbrido |
| [Fan-out](scenarios/fanout/README.md) | Paralelismo de passos, reatribuição após prazo e completude do rastro; determinístico, sem LLM |

## Estrutura de um cenário

```text
scenarios/<assunto>/
  README.md          # pergunta estudada e como executar
  scenario.py        # entrada principal
  agents/            # agentes deste cenário, quando houver
  docker/            # topologia e adaptadores para serviços em contêineres
  benchmarks/        # casos, campanhas e resultados deste assunto
  runtime_metrics/   # análises de eventos específicas deste assunto
```

Crie apenas as pastas necessárias. Arquivos de domínio, regras e dados ficam
junto ao cenário. Mensageria usa clientes do contrato e não precisa declarar agentes.
Os READMEs indicam se a entrada é uma declaração `Scenario` executada por
`./ariadne run` ou um cliente de serviços já iniciados, executado pelo launcher Docker.

Os agentes pertencem ao cenário que define seu comportamento. Mecanismos genéricos
ficam no SDK; medição/exportação compartilhadas ficam em `tools/benchmarking.py`
e [tools/runtime_metrics](../tools/runtime_metrics/README.md).
Não há diretório global de agentes nem cenário agregador de benchmarks.

A seleção BDI isolada é uma [fixture funcional do SDK](../sdk/python/tests/fixtures/route_choice.py),
não um estudo comparativo separado. A antiga campanha A–D foi distribuída entre
os assuntos acima; os rótulos permanecem nos resultados para identificação.
Evidências históricas mantêm os bytes e caminhos registrados na coleta.

[Guia de execução](../docs/quickstart.md) · [Avaliação](../docs/evaluation.md)
