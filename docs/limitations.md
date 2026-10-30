# Escopo e limitações

O projeto é um protótipo de pesquisa de interoperabilidade e cooperação entre
agentes. O contrato e a implementação de referência são o centro da contribuição.

## Runtime

- Registry, broker de mensagens e estado de workflows ficam em memória e são
  perdidos quando os contêineres da execução são removidos.
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

- Toda execução exige Docker com Compose v2; não há modo sem contêineres.
  A primeira execução constrói as imagens e pode levar cerca de um minuto.
- Os contêineres de uma execução ficam na mesma máquina. Isolam sistema de
  arquivos, dependências e rede, mas não medem latência entre hosts.
- Cada execução usa projeto Compose, portas e diretório exclusivos; repetições
  com `--repeat` reutilizam os mesmos contêineres e o estado interno dos agentes.
- O cliente da amostra roda no host contra a porta publicada do Orchestrator;
  os agentes só se comunicam pela rede interna do projeto.
- A imagem genérica de agente instala as dependências do SDK com versões
  fixas, mas não a partir do `uv.lock`.
- Os resultados logísticos publicados cobrem oito casos, duas repetições e um
  modelo. Não estabelecem generalização para outros domínios ou modelos.
- O avaliador logístico compartilha regras de domínio com o BDI. A execução
  declarativa usa a busca genérica do SDK; a avaliação preserva uma busca de
  referência separada. Isso não torna o oráculo totalmente independente.

## Direções de evolução

Executar os contêineres em mais de um host, melhorar proveniência e
relatórios e ampliar a avaliação são próximos incrementos possíveis. Persistência, segurança de transporte e outros modelos
de agentes exigem decisões próprias de escopo.

[Avaliação](evaluation.md) · [Índice](README.md)
