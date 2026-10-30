# Apresentar o projeto

O fio condutor é uma pergunta: **como agentes com arquiteturas internas
diferentes podem cooperar por uma interface comum?** Apresente contrato,
coordenação e lógica dos agentes como partes distintas. Os cenários mostram
comportamentos da implementação; os benchmarks respondem perguntas de avaliação
dentro de uma amostra e de um domínio definidos.

## Preparar a demonstração

Antes da apresentação, execute os cenários escolhidos para construir as imagens
e verificar o ambiente. Guarde os IDs: `./ariadne status` sem argumento sempre mostra
a última execução iniciada, não necessariamente a que está sendo apresentada.

```sh
./ariadne doctor
./ariadne run studies/scenarios/basic_task/scenario.py
./ariadne run studies/scenarios/sequential_workflow/scenario.py
./ariadne run studies/scenarios/failure_reassignment/scenario.py
./ariadne run studies/scenarios/fanout/scenario.py
```

Abra `./ariadne viewer` e escolha uma das missões listadas de `.ariadne/runs`.

Para apresentar sem executar nada, o Viewer também lista as missões preservadas
em `studies/**/results/` e as fixtures de `tools/mission-viewer/fixtures/`.
Para outros cenários, preserve previamente as pastas de resultados. Diga
explicitamente quando estiver mostrando uma execução registrada.

## Roteiro de 10–15 minutos

Os tempos abaixo são uma sugestão de fala, não estimativas de execução ou build.

| Tempo | O que explicar ou fazer | Evidência a mostrar |
|---|---|---|
| 0–2 min | Problema, objetivo e contribuição: contrato comum, runtime e SDK | Diagrama da [arquitetura](architecture.md) e serviços do [contrato](../proto/contract/v1/contract.proto) |
| 2–4 min | Uma tarefa solicita uma capacidade; o runtime encontra e aciona um agente | `./ariadne run studies/scenarios/basic_task/scenario.py`; resultado com `echo` e trace |
| 4–6 min | O runtime também coordena etapas com dependências | Resultado do workflow sequencial, saídas `first` e `second`; definição no [scenario.py](../studies/scenarios/sequential_workflow/scenario.py) |
| 6–8 min | Uma tentativa pode falhar e a política permitir nova atribuição | Visualizador do cenário de falha: `TASK_ASSIGNED`, `TASK_TIMEOUT`, `TASK_REASSIGNED`, `TASK_COMPLETED` |
| 8–11 min | A mesma interface integra interpretação LLM e planejamento BDI | Missão de [rotas](../studies/scenarios/routing/README.md) ou [logística v3](../studies/scenarios/logistics/v3/README.md) no Mission Viewer |
| 11–15 min | Resultados do estudo de caso, alcance e próximos problemas | Tabela e artefatos da [avaliação](evaluation.md), acompanhados das [limitações](limitations.md) |

Para uma conversa curta, use problema → exemplo de recuperação → arquitetura
→ limites. Para uma banca, reserve tempo para metodologia e ameaças à validade.
Os cenários determinísticos usam agentes de teste; eles não demonstram, sozinhos,
cooperação entre raciocínio LLM e BDI.

## Ler uma missão na tela

1. Abra a missão de fan-out ou de rotas no Mission Viewer e mostre o cartão de
   apresentação: título, descrição e o papel de cada agente.
2. Na vista **Dependências**, cada rodada é uma faixa: o planejador à esquerda
   e os passos que ele propôs, ligados por setas de binding.
3. Na vista **Linha do tempo**, cada agente tem uma pista; blocos lado a lado
   executaram em paralelo e a tentativa que estourou o prazo aparece hachurada.
4. Clique num bloco para ver a entrada, a saída e o rastro BDI daquela chamada.
5. Explique por que sucesso final não significa ausência de falhas intermediárias.

O reassignment depende da política e da existência de alternativa. O timeout
não garante que o agente original tenha parado seus efeitos; o cenário não
prova segurança de retry para operações externas não idempotentes.

## Ligar implementação e trabalho escrito

Esta matriz sugere como organizar a argumentação, sem pressupor que o texto
acadêmico tenha esses títulos ou já esteja completo.

| Parte da argumentação | Artefato do repositório | O que sustenta e o que falta |
|---|---|---|
| Problema e objetivo | [Visão geral](../README.md) | Delimita o problema implementado; a motivação científica requer bibliografia e trabalhos relacionados no texto |
| Proposta de interface comum | [Contrato e referência](reference.md) | Expõe mensagens, serviços e configuração; interoperabilidade observada se limita aos consumidores implementados |
| Implementação da solução | [Arquitetura](architecture.md) e [mapa do código](development.md#mapa-do-repositório) | Permite rastrear responsabilidades e decisões; não demonstra por si só qualidade experimental |
| Verificação funcional | [Cenários](scenarios.md), testes e relatórios locais | Mostra comportamentos específicos; registrar falhas também faz parte da evidência |
| Método e resultados | [Avaliação](evaluation.md), mundo, dataset, avaliador e artefatos selecionados | Apoia a análise da execução publicada; declarar amostra, acesso ao modelo, critérios e limitações |
| Discussão e conclusão | [Limitações](limitations.md) | Separa achados observados de hipóteses de evolução e evita extrapolar para outros domínios |

## Perguntas que merecem respostas explícitas

- **O que é interoperável?** A comunicação definida pelo contrato e seus
  consumidores Go/Python. A implementação não traduz automaticamente protocolos
  de qualquer plataforma externa.
- **Onde está o raciocínio?** Nos agentes: BDI simplificado, LLM e regras de
  domínio. O runtime descobre, seleciona, executa e coordena; o planejamento de
  decomposição pode ser delegado explicitamente a um agente.
- **O híbrido é sempre melhor?** A comparação publicada vale para o estudo
  logístico selecionado. BDI recebe missão estruturada; LLM interpreta linguagem
  natural. As entradas e responsabilidades devem acompanhar a comparação.
- **O avaliador é independente?** A checagem é separada da resposta LLM,
  mas compartilha regras de domínio com o BDI. A execução atual usa a busca do
  SDK e a avaliação mantém uma busca de referência; na coleta histórica, ambas
  usavam o mesmo planejador.
- **A latência exibida mede overhead?** O resumo do executor inclui prontidão e
  execução do cliente; a duração do workflow tem outro escopo. Nenhuma delas,
  isoladamente, é uma comparação controlada com e sem runtime.

## Se algo falhar durante a apresentação

Use o ID para consultar `./ariadne logs ID`. Abra os dados disponíveis e identifique
a etapa da falha; um arquivo ausente não deve ser interpretado como aprovação.
Se necessário, passe ao exemplo registrado, explicando a mudança. Para LLM,
prefira preparar uma execução antes: credencial, rede, modelo e resposta são
dependências reais, e novas chamadas podem gerar custo.

O visualizador não executa cenários nem altera resultados. `./ariadne viewer` abre o
[Mission Viewer](../tools/mission-viewer/README.md) com a lista das execuções
de `.ariadne/runs` e dos estudos; clique numa para ver o grafo das rodadas.

## Logística

A versão corrente é a [v3](../studies/scenarios/logistics/v3/README.md), que
roda como missão e aparece no Mission Viewer como as demais. A v2 é um estudo
histórico: suas [figuras](../studies/scenarios/logistics/v2/results/presentation/README.md),
o [roteiro](../studies/scenarios/logistics/v2/docs/presentation.md) e o
[relatório do híbrido enxuto](../studies/scenarios/logistics/v2/results/stress-lean/README.md)
continuam disponíveis como material preservado. Apresente o nome da
configuração e a cobertura da coleta ao comparar resultados.

[Índice](README.md) · [Primeira execução](quickstart.md) · [Avaliação](evaluation.md)
