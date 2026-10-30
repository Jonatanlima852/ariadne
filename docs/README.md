# Documentação do Ariadne Runtime

Esta documentação descreve a implementação atual e os caminhos para executar,
entender, desenvolver e avaliar o projeto. Todos os comandos partem da raiz
do repositório, salvo indicação explícita.

## Caminhos de leitura

| Objetivo | Sequência sugerida |
|---|---|
| Executar pela primeira vez | [Primeira execução](quickstart.md) → [cenários](scenarios.md) |
| Entender a solução | [Arquitetura](architecture.md) → [contrato e configuração](reference.md) |
| Alterar o código | [Desenvolvimento](development.md) → referência e testes do componente |
| Avaliar o TCC | [Avaliação](evaluation.md) → artefatos → [limitações](limitations.md) |
| Apresentar para outras pessoas | [Roteiro](presentation.md) → [Mission Viewer](../tools/mission-viewer/README.md) |

## Guias e referência

- [BDI declarativo e planejamento](bdi.md): entradas, planos, seleção e busca genérica no SDK.

- [Experimentos declarativos](experiments.md): agentes e cenário em um arquivo,
  execução em contêineres pelo runtime Go e evidências brutas para avaliação separada.
- [Estudo logístico](../studies/scenarios/logistics/README.md): v3 como missão do runtime,
  campanha, análise e a v2 histórica.

- [Primeira execução](quickstart.md): requisitos, primeiro comando, resultado e diagnóstico.
- [Executor ariadne](cli.md): comandos, o que `run` faz nos contêineres e arquivos de resultado.
- [Arquitetura e conceitos](architecture.md): responsabilidades, fluxos e glossário.
- [Catálogo de cenários](scenarios.md): objetivos, requisitos e resultados esperados.
- [Desenvolvimento](development.md): mapa do código, ambiente, SDK e verificações.
- [Contrato e configuração](reference.md): APIs, versões, políticas e variáveis.
- [Avaliação e evidências](evaluation.md): perguntas, resultados e reprodução.
- [Apresentação](presentation.md): roteiro de demonstração, leitura dos resultados e vínculo ao TCC.
- [Mission Viewer](../tools/mission-viewer/README.md): página estática com grafo de dependências, linha do tempo por agente e rótulos de apresentação.
- [Escopo e limitações](limitations.md): fronteiras operacionais e experimentais.

## Como manter estes guias

Ao mudar uma API, configuração ou comando, atualize o guia correspondente.
Os READMEs dos cenários são a referência para suas topologias; este índice
aponta para eles. Resultados publicados devem identificar sua execução e
permanecer distintos de expectativas de uma nova coleta.

`internal-notes/` é o acervo interno de aprendizado e acompanhamento do autor.
Pode conter propostas antigas e arquivos somente locais. Nenhum guia público
depende de sua leitura. O contrato executável está no `.proto` e o comportamento
atual pode ser consultado nos arquivos de implementação vinculados nestas páginas.

[Voltar ao projeto](../README.md)
