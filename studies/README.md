# Estudos por cenário

Cada cenário reúne sua definição, agentes específicos, domínio, regras, casos,
configuração de execução, benchmarks e métricas. Não há separação por tamanho
ou por ser uma demonstração: todos fazem parte dos estudos do TG.

## Cenários

| Cenário | O que investigar |
|---|---|
| [Tarefa simples](scenarios/basic_task/README.md) | Descoberta, atribuição e resposta |
| [Workflow sequencial](scenarios/sequential_workflow/README.md) | Dependências e passagem de resultados |
| [Recuperação](scenarios/failure_reassignment/README.md) | Prazo e nova atribuição |
| [Mensageria](scenarios/messaging/README.md) | Envelopes, entrega e correlação |
| [Rotas BDI](scenarios/bdi_route/README.md) | Seleção de planos por custo |
| [Saudação LLM](scenarios/llm_greeting/README.md) | Resposta estruturada de um provedor |
| [Agendamento](scenarios/meeting/README.md) | Crenças, restrições e planos |
| [Rota heterogênea](scenarios/heterogeneous_route/README.md) | Cooperação LLM → BDI → LLM |
| [Logística](scenarios/logistics/README.md) | Estratégias BDI, LLM e híbrida em um domínio comum |
| [Comparação do runtime](scenarios/runtime_comparison/README.md) | Campanha histórica A–E de capacidades do runtime |

## Onde colocar cada artefato

- Agentes reutilizáveis: [agents/](agents/README.md).
- Agentes e regras exclusivos: dentro do cenário correspondente.
- Campanhas e resultados selecionados: `scenarios/<nome>/benchmarks/`.
- Análise de eventos de um cenário: `scenarios/<nome>/runtime_metrics/`.
- Cálculo genérico de métricas: [tools/runtime_metrics](../tools/runtime_metrics/README.md).

Crie apenas as pastas necessárias. Os mecanismos de execução e campanha são
fornecidos pelo SDK. Novas execuções continuam usando `.ariadne/`; resultados
selecionados podem ser preservados no cenário com origem e limitações descritas.
Caminhos históricos dentro de evidências permanecem intactos.

[Guia de execução](../docs/quickstart.md) · [Avaliação](../docs/evaluation.md)
