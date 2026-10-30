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
./ariadne demo
./ariadne scenario workflow-sequential
./ariadne scenario failure-reassignment
```

Inicie a API e o frontend conforme o
[guia do visualizador](../tools/inspector/README.md), abra
`http://127.0.0.1:4173` e escolha uma das execuções listadas de `.ariadne/runs`.

Para apresentar sem Docker, escolha um item no catálogo **Demonstrações**.
Ele mostra registros reais incluídos no repositório e identificados como exemplos.
Para outros cenários, preserve previamente as pastas de resultados. Diga
explicitamente quando estiver mostrando uma execução registrada.

## Roteiro de 10–15 minutos

Os tempos abaixo são uma sugestão de fala, não estimativas de execução ou build.

| Tempo | O que explicar ou fazer | Evidência a mostrar |
|---|---|---|
| 0–2 min | Problema, objetivo e contribuição: contrato comum, runtime e SDK | Diagrama da [arquitetura](architecture.md) e serviços do [contrato](../proto/contract/v1/contract.proto) |
| 2–4 min | Uma tarefa solicita uma capacidade; o runtime encontra e aciona um agente | `./ariadne demo`; resultado com `execution-simulator-01` e trace |
| 4–6 min | O runtime também coordena etapas com dependências | Resultado de `workflow-sequential`, saídas `first` e `second`; definição no [script](../studies/scenarios/sequential_workflow/docker/scenario.py) |
| 6–8 min | Uma tentativa pode falhar e a política permitir nova atribuição | Visualizador do cenário de falha: `TASK_ASSIGNED`, `TASK_TIMEOUT`, `TASK_REASSIGNED`, `TASK_COMPLETED` |
| 8–11 min | A mesma interface integra interpretação LLM e planejamento BDI | Fluxo heterogêneo na arquitetura e, se preparado, relatório de `heterogeneous-route` ou `logistics-mission` |
| 11–15 min | Resultados do estudo de caso, alcance e próximos problemas | Tabela e artefatos da [avaliação](evaluation.md), acompanhados das [limitações](limitations.md) |

Para uma conversa curta, use problema → exemplo de recuperação → arquitetura
→ limites. Para uma banca, reserve tempo para metodologia e ameaças à validade.
Os cenários determinísticos usam agentes de teste; eles não demonstram, sozinhos,
cooperação entre raciocínio LLM e BDI.

## Ler o cenário de recuperação na tela

1. Abra a demonstração de recuperação e apresente o pedido e os dois agentes.
2. Clique em **Reproduzir**: a tarefa chega ao primeiro agente, o prazo esgota
   e o Ariadne atribui o trabalho ao agente alternativo. Use as setas para pausar
   a explicação em cada acontecimento.
3. Mostre a resposta em **Desfecho registrado**, separada do instante do replay.
   O ritmo da animação é didático; os tempos reais aparecem na legenda.
4. Explique por que sucesso final não significa ausência de falhas intermediárias.
5. Em **Detalhes técnicos**, abra a linha do tempo ou os dados brutos para
   relacionar a figura aos IDs e eventos originais.

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

O visualizador não executa cenários nem altera resultados. Na aba **Logística v2**,
ele também compara as métricas já registradas por caso e configuração.
Para missões (contrato 2.0.0), `make viewer` abre o
[Mission Viewer](../tools/mission-viewer/README.md) com a lista das execuções
de `.ariadne/runs` e dos estudos; clique numa para ver o grafo das rodadas.

## Logística com mais agentes

As [figuras da logística v2](../studies/scenarios/logistics/v2/results/presentation/README.md)
incluem PNG/SVG para slides, animação e um player HTML que abre sem serviços.
O [roteiro específico](../studies/scenarios/logistics/v2/docs/presentation.md) reúne
o resumo quantitativo e a explicação do percurso. A confirmação concluiu 60
observações e está documentada com suas exceções e limites no
[relatório do híbrido enxuto](../studies/scenarios/logistics/v2/results/stress-lean/README.md).
O cenário original tem dez especialistas; a
[configuração enxuta](../studies/scenarios/logistics/v2/docs/lean.md) tem um LLM e sete
BDI. Mostre o percurso de uma tarefa, a interrupção por incidente e o novo
planejamento antes de apresentar os totais do benchmark.

No Inspector, selecione **Logística v2**, uma observação e **Percurso dos agentes**.
As setas mostram tarefas e respostas passando pelo runtime. IDs, bindings e
estado do episódio permitem relacionar a figura às evidências. O ritmo do player
é didático e não representa a duração das chamadas.

A [pasta de resultados](../studies/scenarios/logistics/v2/results/README.md)
separa suíte básica, desenvolvimento, coleta interrompida e confirmação. Apresente
o nome da configuração e a cobertura da coleta ao comparar resultados. A equipe
original não ganha por simplesmente ter mais agentes; a versão enxuta investiga
uma divisão de responsabilidades diferente, com menos chamadas LLM no caminho
crítico e uma política energética revisada.

[Índice](README.md) · [Primeira execução](quickstart.md) · [Avaliação](evaluation.md)
