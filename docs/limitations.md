# Escopo e limitações

O projeto é um protótipo de pesquisa de interoperabilidade e cooperação entre
agentes. O contrato e a implementação de referência são o centro da contribuição.

## Runtime

- Registry, broker de mensagens e estado de workflows ficam em memória e são
  perdidos ao reiniciar os processos.
- Messaging oferece entrega at-most-once, com um stream ativo por destinatário,
  sem confirmação de processamento ou reentrega durável.
- A detecção de falhas usa timeouts fixos. Uma pausa longa pode levar a suspeita.
- Timeout de uma tentativa não garante interrupção dos efeitos de um agente;
  tarefas com efeitos externos exigem considerar idempotência antes de retry.
- Workflows são DAGs limitados, sem loops arbitrários, compensação ou rollback.
- Não há autenticação, autorização ou TLS na topologia experimental.

## Agentes e domínio

- `BdiAgent` é uma abstração BDI simplificada, não um interpretador completo
  AgentSpeak/Jason.
- A otimalidade no experimento logístico decorre do planejador de custo uniforme
  e das regras desse domínio; não é uma propriedade geral de qualquer agente BDI.
- Uma interpretação LLM incorreta pode produzir uma missão diferente da intenção
  humana, mesmo que o plano seja válido para a missão estruturada recebida.
- Latência e saídas LLM dependem do modelo, prompt, provedor e condições de rede.

## Uso e avaliação atuais

- No caminho manual, o Compose básico exige conferir prontidão pelos logs.
  `./ariadne` verifica endpoints e registro dos agentes antes de executar o cenário.
- O cliente genérico não apresenta workflows; use os scripts ou `RuntimeClient`.
- A suíte A–D inclui chamadas LLM e exige credencial mesmo contendo casos
  determinísticos. Os cenários individuais sem LLM continuam disponíveis.
- Os runners de benchmarks reutilizam um volume de eventos. Uma nova coleta
  deve começar em ambiente isolado ou com limpeza deliberada após preservar dados.
  Os cenários via `./ariadne` já usam volumes e diretórios exclusivos por execução;
  isso não altera o comportamento dos runners de benchmark.
- Dependências instaladas por alguns Dockerfiles não seguem os locks locais.
- Os resultados logísticos publicados cobrem oito casos, duas repetições e um
  modelo. Não estabelecem generalização para outros domínios ou modelos.
- O avaliador logístico compartilha regras de domínio com o BDI. A execução
  declarativa usa a busca genérica do SDK; a avaliação preserva uma busca de
  referência separada. Isso não torna o oráculo totalmente independente.

## Direções de evolução

Ampliar o isolamento às campanhas de benchmark, melhorar proveniência e
relatórios, automatizar verificações e ampliar a avaliação são próximos
incrementos possíveis. Persistência, segurança de transporte e outros modelos
de agentes exigem decisões próprias de escopo.

[Avaliação](evaluation.md) · [Índice](README.md)
