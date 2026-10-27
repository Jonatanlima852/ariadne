# Material para a apresentação

## Abrir primeiro

- **[Índice visual offline](../results/presentation/index.html)**: abre no navegador e reúne resumo, players e figuras.
- **[Resumo quantitativo PNG, 16:9](../results/stress-lean/analysis/headline.png)** e [SVG](../results/stress-lean/analysis/headline.svg): figura pronta para o slide de resultados.
- [Percurso offline da arquitetura enxuta](../results/presentation/s08-ariadne-lean/flow.html): oito agentes, dez pedidos e três incidentes. Clique em **Reproduzir** ou escolha os quadros na coluna da direita.
- [Panorama PNG](../results/presentation/s08-ariadne-lean/overview.png) e [SVG vetorial](../results/presentation/s08-ariadne-lean/overview.svg) para colocar no slide.
- [Pane registrada](../results/presentation/s08-ariadne-lean/incident.png) e [recuperação da carga](../results/presentation/s08-ariadne-lean/recovery.png) para explicar a revisão.
- [Animação GIF](../results/presentation/s08-ariadne-lean/flow.gif) se preferir inserir a reprodução no slide.
- [Versão original com dez agentes](../results/presentation/s07-ariadne/flow.html), com [panorama](../results/presentation/s07-ariadne/overview.png), [GIF](../results/presentation/s07-ariadne/flow.gif) e seus próprios dados.

Os HTMLs abrem diretamente no navegador e não precisam de Docker, rede, API ou
uma nova resposta do modelo. Os GIFs mostram a sequência completa. A seleção dos
quadros permite saltar para a pane e a transferência sem esperar a animação toda.

O [guia das figuras](../results/presentation/README.md) registra a origem, os IDs e
os comandos de regeneração. As duas figuras ilustram arquiteturas em casos
diferentes; a comparação quantitativa usa os mesmos casos em ambos os lados.

## Resultado medido para apresentar

A confirmação concluiu os dez casos com três repetições por configuração:
60 observações, com o mesmo modelo, mundo, regras e limites.

| Métrica | Single LLM | Híbrido enxuto |
|---|---:|---:|
| Tempo real médio por episódio | 87,08 s | 4,88 s |
| Tokens médios nos mesmos 29 pares com uso conhecido | 18.395 | 1.038 |
| Pedidos entregues | 204/228 | 219/228 |
| Entregues no prazo | 190/228 | 210/228 |
| Ações rejeitadas | 13 | 0 |
| Episódios com erro operacional | 1 | 0 |

“Nesta suíte, a divisão entre interpretação LLM e planejamento BDI reduziu o
tempo médio por um fator de 17,8 e os tokens em 94,4% nos pares com uso medido,
mantendo maior atendimento e pontualidade agregados.”

Há um timeout no Single LLM, preservado na análise. Sem o par desse timeout,
a vantagem de tempo continua em 18,0 vezes. No caso específico de prazos,
o Single teve mais entregas pontuais: 17/24 contra 15/24. Essas duas observações
devem acompanhar a interpretação, sem alegar vantagem universal.

O [relatório completo](../results/stress-lean/README.md) traz cobertura, sensibilidade,
diferenças por caso e limites. Os [gráficos por caso](../results/stress-lean/analysis/analysis.md)
e CSVs permitem conferir os números. O status `FAILED` do manifesto corresponde
ao episódio com timeout; a coleta tem 60/60 observações concluídas.

## Explicação da circulação das informações

“O pedido entra em linguagem natural. O OrderInterpreter LLM o transforma em
requisitos estruturados, conferidos pelo controlador. O MissionCoordinator BDI
ordena o trabalho pendente. O runtime encaminha a tarefa ao InventoryManager,
que devolve opções de estoque; essas opções alimentam a alocação de veículo.
A alocação alimenta a rota, a rota passa pela verificação energética e a sequência
completa é simulada pelo supervisor. Só uma sequência aprovada chega ao executor.
Quando ocorre uma pane, o executor interrompe as ações; o estado e a ocorrência
alimentam uma nova coordenação e um novo workflow. Outro veículo pode recuperar
a carga, e a entrega só é registrada após uma ação DELIVER válida.”

As setas passam pelo orquestrador. A contribuição do runtime é descobrir
capacidades, encaminhar tarefas e coordenar bindings entre resultados. As
decisões de domínio pertencem aos agentes. Os círculos contam chamadas; eles
não representam um agente diferente para cada pedido.

## Sequência sugerida de slides

1. **Problema:** combinar interpretação de linguagem e planejamento com regras,
   sem obrigar todos os agentes a usar a mesma arquitetura interna.
2. **Implementação:** panorama dos oito agentes, cada um em seu contêiner,
   com um LLM e sete BDI usando o mesmo contrato do Ariadne.
3. **Cooperação observada:** player ou dois quadros, mostrando interrupção,
   nova coordenação e recuperação por TRANSFER.
4. **Comparação medida:** mesmos dez casos, mesmo modelo e regras, três
   repetições por configuração; tempo real, tokens e atendimento apresentados
   separadamente.
5. **Interpretação:** a divisão de trabalho e a política de energia foram
   revisadas; a composição original com mais LLMs teve custos maiores.

## Usar o Inspector

```sh
./ariadne inspect
```

Abra `http://127.0.0.1:4173/#source=logistics`, selecione a coleta e a observação,
e escolha **Percurso dos agentes**. Use **Panorama para apresentação** para
exibir a arquitetura inteira; **Baixar figura SVG** exporta o quadro atual.
As outras abas mostram histórico, prazos e decisões completas. **Atualizar
coleta** preserva o contexto selecionado.

Para uma apresentação previsível, use os arquivos preservados. Abrir o player
não inicia novas chamadas LLM. O ritmo da animação é didático: segundos de
reprodução, tempo real das chamadas e minutos simulados são medidas diferentes.

## Explicar a revisão da arquitetura

A [versão enxuta](lean.md) retoma a divisão de responsabilidades do estudo
logístico anterior: linguagem com LLM e planejamento com BDI. O problema da
primeira versão com dez especialistas era, em parte, consultar LLMs novamente
para falhas de viabilidade já detectadas simbolicamente. Além disso, a política
energética podia deixar veículos sem autonomia de saída após a entrega.

A revisão removeu decomposição, análise de incidentes e relato por LLM do
caminho crítico. Acrescentou um coordenador BDI e uma reserva para alcançar
carregador enquanto houver trabalho pendente. O [protocolo fixado](../experiments/lean-v1-confirmation.json)
preserva casos, limites, hashes e imagens dos contêineres usados.

## Responder a perguntas da banca

- **São agentes independentes?** Sim: módulos, contêineres e capacidades
  registradas separadamente. O controlador envia tarefas pelo SDK.
- **O runtime planeja as rotas?** As rotas são decisões dos agentes. O runtime
  resolve capacidades e dependências de execução.
- **Por que o Single LLM usa mais tokens?** Ele gera a sequência de ações no
  contrato estruturado e recebe estado atualizado nas revisões. O híbrido gera
  requisitos e executa o planejamento em código. Esse custo pertence à divisão
  de trabalho comparada; não prova superioridade intrínseca de raciocínio.
- **O resultado vale para qualquer problema?** A evidência é desta suíte fixa,
  usada no desenvolvimento. Repetições medem variação nestes casos, e a política
  simbólica não garante solução global ótima.
- **Pode haver um caso em que o Single LLM seja melhor?** Sim. Atendimento,
  pontualidade, distância, energia e tempo são objetivos diferentes. Os gráficos
  mantêm os resultados desfavoráveis ao híbrido.
- **Uma entrega parcial é necessariamente erro?** Não. Dois casos contêm
  restrições que impedem atendimento total. Timeouts e outras falhas operacionais
  são registrados separadamente, sem transformar valores desconhecidos em zero.

O [catálogo de resultados](../results/README.md) separa demonstração determinística,
coletas de desenvolvimento e confirmação. O relato de um LLM não substitui o
histórico validado das ações.
