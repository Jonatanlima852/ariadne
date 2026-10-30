# Guia de avaliação e evidências

## Proposta do trabalho

O trabalho investiga se um contrato comum, apoiado por um runtime distribuído,
permite a cooperação entre agentes com arquiteturas internas diferentes.
A contribuição reúne contrato, implementação de referência, SDK e avaliação
experimental. O domínio logístico é um estudo de caso dessa infraestrutura.

## Roteiro de leitura e demonstração

O [roteiro de apresentação](presentation.md) organiza uma fala de 10–15 minutos
e relaciona os artefatos à argumentação acadêmica. Para inspecionar uma execução
de missão, use o [Mission Viewer](../tools/mission-viewer/README.md); ele mostra
eventos e resultados, sem recalcular métricas dos benchmarks.

1. Leia a [arquitetura](architecture.md) e a separação entre runtime e agentes.
2. Execute a [tarefa básica](quickstart.md) para conferir a integração.
3. Observe [workflow](../studies/scenarios/sequential_workflow/README.md) e
   [reassignment](../studies/scenarios/failure_reassignment/README.md) sem LLM.
4. Execute a [rota heterogênea](../studies/scenarios/routing/README.md) e o
   [fan-out](../studies/scenarios/fanout/README.md); a rota usa o modelo real
   caso haja credencial, ou o substituto com `ROUTING_DEMO=1`.
5. Consulte os resultados logísticos já registrados e suas limitações.

Ler os artefatos selecionados não exige executar nada nem chamadas externas. Uma nova
coleta LLM é uma nova observação: não se espera igualdade exata de latências e
respostas com a execução publicada.

## Perguntas e evidências

| Pergunta | Onde conferir | Alcance |
|---|---|---|
| Agentes heterogêneos cooperam pelo contrato? | [Cenário de rota](../studies/scenarios/routing/scenario.py) e [contrato](../proto/contract/v1/contract.proto) | Agentes BDI-like e LLM utilizados nos exemplos |
| O runtime recupera uma tarefa após timeout? | [Cenário de falha](../studies/scenarios/failure_reassignment/scenario.py), eventos e [testes do executor](../runtime/services/orchestrator/internal/execution/executor_test.go) | Recuperação conforme retry e existência de alternativa |
| Políticas alteram a distribuição? | [Seleção de agentes](../studies/scenarios/agent_selection/scenario.py) com `POLICY` | Três agentes com carga reportada configurada |
| O híbrido melhora propriedades do plano? | [Resultados logísticos](../studies/scenarios/logistics/results/logistics-20261004T-final-v2/logistics-summary.csv) | Mundo, dataset, modelo e amostra utilizados |
| Qual é o overhead do runtime? | Requer comparação controlada da mesma tarefa com e sem runtime | O caso E compara fluxos diferentes e não isola esse custo |

Os testes automatizados verificam comportamentos específicos. Eles não
substituem uma avaliação experimental nem provam generalidade dos resultados.

## Logística v3: missão no laço do orquestrador

A avaliação atual do estudo logístico é a [v3](../studies/scenarios/logistics/v3/README.md).
Ela responde à crítica feita à v2 (o laço de episódio vivia em um controlador
Python e a variante enxuta reduzia o LLM a interpretação): o laço passa a ser
a missão do contrato 2.0.0, executada pelo orquestrador Go. As duas
configurações usam o mesmo domínio, os mesmos casos (`basic` e `stress` da
v2) e o mesmo modelo:

- `ariadne-v3`: um planejador LLM (`mission-planning`) interpreta os pedidos,
  decide quais atacar em paralelo e delega cada um a um agente BDI
  deliberativo (`logistics-v3-delivery`, três instâncias); um executor
  determinístico (`logistics-v3-execute`) aplica as propostas, rejeita ações
  inválidas e dispara incidentes; o novo estado volta ao planejador pelo
  contexto da missão e ele replaneja ou responde `DONE`.
- `single-llm-v3`: o Single LLM da v2, com o mesmo prompt, embrulhado como
  planejador de missão que emite um único passo `execute` por rodada.

O que se compara, por caso e configuração: pedidos entregues e no prazo,
ações rejeitadas, distância, energia, tempo real, rodadas, chamadas e tokens
do planejador, ciclos de deliberação BDI, passos paralelos por rodada e
reatribuições. Tudo sai do `MissionResult` de cada missão, salvo inteiro em
`missions/` e legível no [visualizador de missão](../tools/mission-viewer/README.md).

```sh
# sem credencial: substitutos determinísticos (não mede um modelo)
LOGISTICS_V3_DEMO=1 ./ariadne run studies/scenarios/logistics/v3/scenario.py

# campanha real: cada observação sobe sua topologia em contêineres;
# exporte OPENAI_API_KEY (e LLM_MODEL) no terminal, o executor repassa aos agentes
uv run --project sdk/python python -m studies.scenarios.logistics.v3.benchmarks.run \
  --suite stress --configurations ariadne-v3 single-llm-v3 --repeat 3
python -m studies.scenarios.logistics.v3.benchmarks.analyze \
  --input .ariadne/logistics-v3/<coleta>/results.json --output /tmp/logistics-v3-analysis --no-plots
```

Para avaliar: separe `execution_kind` demo de real; compare atendimento e
prazo antes de custos; leia rodadas e rejeições junto com os incidentes de
cada caso; use `comparison.md` da coleta para as colunas que o analisador da
v2 não cobre (rodadas, ciclos BDI, paralelismo, reatribuições). Não há
resultados reais da v3 registrados ainda; as tabelas abaixo são históricas.

## Paralelismo, reatribuição e rastro

O [estudo de fan-out](../studies/scenarios/fanout/README.md) isola três
propriedades do runtime sem LLM: a execução paralela de passos
independentes de uma missão, a reatribuição de um passo cujo agente não
cumpriu o prazo e a completude do rastro de eventos. A missão conta as
palavras de um texto dividido em N fragmentos: um planejador determinístico
pede N passos `map` em paralelo e um `reduce` dependente de todos; K
contadores idênticos oferecem a capacidade, e um contador lento, com a mesma
capacidade, demora mais que o prazo do passo. As métricas saem do
`mission-result.json` (intervalos por passo) e do `events.jsonl`
(`TASK_TIMEOUT`, `TASK_REASSIGNED`, conjunto esperado por missão):

- speedup e fator de paralelismo por K (varredura K em {1, 2, 4, 8});
- contagem de reatribuições, detecção do prazo, recuperação
  (`TASK_REASSIGNED - TASK_TIMEOUT`) e conclusão após o timeout, com
  mediana, média, desvio e p95 entre repetições;
- completude do rastro: eventos esperados presentes sobre esperados;
- um Gantt por amostra com os passos por agente e a tentativa reatribuída.

```sh
./ariadne run studies/scenarios/fanout/scenario.py --repeat 5
./ariadne campaign studies/scenarios/fanout/campaign.py
uv run --project sdk/python python -m studies.scenarios.fanout.analysis studies/scenarios/fanout/campaigns/campaign-<id> --output <analysis>
```

Resultados de 29 de outubro de 2026 em
[results/2026-10-29-ready-queue](../studies/scenarios/fanout/results/2026-10-29-ready-queue/README.md):
speedup 1,99, 3,84 e 7,31 para K = 2, 4 e 8 (N = 8, 300 ms por fragmento);
recuperação mediana de 2,0 ms e p95 de 2,6 ms em oito prazos estourados;
rastro completo em todas as missões. A coleta anterior, com o engine de ondas
com barreira, fica em
[results/2026-10-29](../studies/scenarios/fanout/results/2026-10-29/README.md)
como o "antes": com o contador lento, o tempo de parede mediano caiu de
3.661 ms para 2.166 ms ao trocar as ondas pela fila de prontos. O trabalho é simulado (`sleep`), a
coleta é local e só a falha por prazo é exercitada; leia as limitações no
README do estudo.

## Resultados logísticos selecionados (histórico: v1 e v2)

As tabelas desta seção registram as avaliações anteriores (v1 com workflow
fixo; v2 com controlador Python) e não representam a avaliação atual.

Execução `logistics-20261004T-final-v2`, registrada em 4 de outubro de 2026:
oito casos, duas repetições e 16 respostas por estratégia, com modelo
`gpt-5.6-luna`. As estratégias são:

- BDI-only: recebe a missão estruturada e usa planejamento simbólico.
- LLM-only: recebe pedido natural e mundo e propõe uma sequência de ações.
- Híbrido: LLM interpreta restrições; BDI planeja a missão estruturada.

A avaliação atual compara apenas LLM-only e híbrido. BDI-only foi retirado da
coleta; aparece abaixo exclusivamente para preservar o registro histórico,
não como estratégia da avaliação atual do TG.

| Estratégia | Validade | Otimalidade agregada¹ | Consistência² | Latência média | Tokens totais |
|---|---:|---:|---:|---:|---:|
| BDI-only | 100% | 100% | 100% | 25,7 ms | 0 |
| LLM-only | 100% | 56,25% | 25% | 4.869,5 ms | 17.170 |
| Híbrido | 100% | 100% | 100% | 1.956,9 ms | 5.282 |

¹ A métrica publicada conta também rejeições corretas de missões impossíveis
como respostas ótimas. Não é uma taxa restrita aos casos viáveis.

² Compara respostas repetidas do mesmo caso; há somente duas repetições por
caso, e o texto de rejeição participa da comparação.

A interpretação estrita do híbrido foi 87,5%. Nos desvios registrados, A foi
incluído como visita obrigatória redundante, pois já é a posição inicial.
Todas as estratégias produziram respostas válidas nessa amostra. A diferença
observada foi de otimalidade, repetibilidade, latência e tokens; esta execução
não demonstra que a LLM tenha produzido planos inseguros.

Artefatos para inspeção:

- [JSON de respostas e avaliações](../studies/scenarios/logistics/results/logistics-20261004T-final-v2/logistics-results.json)
- [Sumário CSV](../studies/scenarios/logistics/results/logistics-20261004T-final-v2/logistics-summary.csv)
- [Gráfico registrado](../studies/scenarios/logistics/results/logistics-20261004T-final-v2/logistics-quality.svg)
- [Eventos JSONL](../studies/scenarios/logistics/results/logistics-20261004T-final-v2/events.jsonl)
- [Mundo](../studies/scenarios/logistics/datasets/world.json), [casos](../studies/scenarios/logistics/datasets/cases.json) e [avaliador](../studies/scenarios/logistics/domain/simulation.py)

Na coleta publicada, o avaliador compartilhava regras e planejador com o BDI.
Na execução declarativa atual, o BDI usa a busca genérica do SDK e o avaliador
mantém a busca de referência; as regras continuam compartilhadas.
Além disso, no caminho de plano executável, `safe` exige que o estado final
satisfaça o objetivo; não mede exclusivamente a aplicabilidade das transições.
Essas convenções devem acompanhar qualquer uso das métricas publicadas.

## Executar uma nova campanha

Na interface declarativa, `./ariadne run arquivo.py --repeat N` preserva as amostras
brutas e logs correlacionados. A avaliação e os gráficos são feitos depois,
em código separado. O [guia de experimentos](experiments.md) descreve os
arquivos, os escopos de duração e a reutilização de estado entre repetições.
Os artefatos publicados permanecem intactos. A coleta não executa BDI isolado nem a comparação do caso E.

O caminho atual do estudo está em [studies/scenarios/logistics](../studies/scenarios/logistics/README.md):

```sh
ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py
ARIADNE_SDK_EXTRAS=llm ./ariadne campaign studies/scenarios/logistics/campaign.py
python3 -m studies.scenarios.logistics.analysis studies/scenarios/logistics/campaigns/campaign-ID
```

Os dois primeiros comandos usam o fluxo híbrido por padrão e fazem chamadas LLM.
O guia do estudo explica como selecionar LLM-only e exportar as credenciais. Substitua `logistics-ID`
pelo diretório informado na coleta. A avaliação usa os dados preservados nos
manifestos e escreve em uma pasta nova; não inicia agentes. No novo caminho,
todas as estratégias usam workflows, portanto os escopos de latência diferem
da campanha histórica. Consistência fica indefinida quando há uma só observação.

### Campanhas por assunto

Cada cenário coleta pela mesma interface: `./ariadne campaign arquivo.py` para
uma matriz de execuções independentes, ou o coletor do estudo, que chama o
mesmo executor por observação. Cada observação sobe sua própria topologia em
contêineres e termina com manifesto, eventos e logs:

```sh
./ariadne campaign studies/scenarios/basic_task/campaign.py
./ariadne campaign studies/scenarios/fanout/campaign.py
uv run --project sdk/python python -m studies.scenarios.logistics.v3.benchmarks.run --demo --suite basic
```

Rotas, logística e saudação exigem `OPENAI_API_KEY` exportada quando não usam
a variável de demonstração; as demais não chamam LLM. A antiga suíte A–D em
Docker, sem manifesto, foi removida; seus rótulos permanecem apenas nas
evidências históricas.

## Interpretar e apresentar

Separe conclusão operacional, validade no domínio e conclusão de pesquisa.
Identifique a execução em cada tabela e gráfico. Preserve dados antigos ao
alterar critérios de medição e declare as [limitações](limitations.md).

[Índice](README.md)
