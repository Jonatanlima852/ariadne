# Estudo logístico

Pedidos em linguagem natural, veículos com bateria e capacidade, depósitos,
prazos e incidentes durante a execução. É o estudo de caso principal do TG e
tem duas versões neste diretório.

| Versão | Estado | O que é |
|---|---|---|
| [v3](v3/README.md) | **corrente** | O estudo como missão do contrato 2.0.0: planejador LLM, entregadores BDI deliberativos em paralelo e executor determinístico, contra um único LLM embrulhado como planejador. Roda com `./ariadne run` e `./ariadne campaign`. |
| [v2](v2/README.md) | histórica | Os mesmos casos, sob o contrato 1.0.0, com o laço de episódio num controlador Python e BDI de um ciclo. Não é mais executável; código, casos e resultados ficam preservados para leitura e comparação. |

Houve uma v1 (um pedido, workflow fixo de interpretação LLM e plano BDI,
oito casos), removida do repositório; sua coleta de 4 de outubro de 2026 está
no histórico do Git.

## Pergunta

Cooperar pelo runtime, com um planejador LLM e especialistas BDI, atende
melhor os pedidos, com menos chamadas e tokens, do que um único LLM decidindo
todas as ações?

## Executar

```sh
LOGISTICS_V3_DEMO=1 ./ariadne run studies/scenarios/logistics/v3/scenario.py
```

Veja o [README da v3](v3/README.md) para variáveis, campanha e análise.

## O que a v2 mostrou

Na suíte básica (um a três pedidos), Single LLM e equipe de especialistas
empataram em entregas e a equipe custou mais tempo e tokens. Na suíte de
estresse (seis a dez pedidos, incidentes), a variante enxuta entregou
219 contra 204 de 228 pedidos, com tempo médio 17,8 vezes menor e 94% menos
tokens. A vantagem cresceu com a dificuldade dos casos. Essa cooperação era
coordenada por código do estudo, sem paralelismo nem deliberação; a v3 repete
os casos com a coordenação feita pelo runtime.

[Todos os estudos](../../README.md) · [Avaliação do TCC](../../../docs/evaluation.md)
