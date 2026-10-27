# Guia de avaliação e evidências

## Proposta do trabalho

O trabalho investiga se um contrato comum, apoiado por um runtime distribuído,
permite a cooperação entre agentes com arquiteturas internas diferentes.
A contribuição reúne contrato, implementação de referência, SDK e avaliação
experimental. O domínio logístico é um estudo de caso dessa infraestrutura.

## Roteiro de leitura e demonstração

O [roteiro de apresentação](presentation.md) organiza uma fala de 10–15 minutos
e relaciona os artefatos à argumentação acadêmica. Para inspecionar uma execução
de cenário, use o [visualizador local](../tools/inspector/README.md); ele mostra
eventos e resultados, sem recalcular métricas dos benchmarks.

1. Leia a [arquitetura](architecture.md) e a separação entre runtime e agentes.
2. Execute a [tarefa básica](quickstart.md) para conferir a integração.
3. Observe [workflow](../studies/scenarios/sequential_workflow/docker/README.md) e
   [reassignment](../studies/scenarios/failure_reassignment/docker/README.md) sem LLM.
4. Execute a [rota heterogênea](../studies/scenarios/routing/docker/README.md),
   caso haja credencial e acesso ao provedor.
5. Consulte os resultados logísticos já registrados e suas limitações.

Ler os artefatos selecionados não exige Docker nem chamadas externas. Uma nova
coleta LLM é uma nova observação: não se espera igualdade exata de latências e
respostas com a execução publicada.

## Perguntas e evidências

| Pergunta | Onde conferir | Alcance |
|---|---|---|
| Agentes heterogêneos cooperam pelo contrato? | [Cenário de rota](../studies/scenarios/routing/scenario.py) e [contrato](../proto/contract/v1/contract.proto) | Agentes BDI-like e LLM utilizados nos exemplos |
| O runtime recupera uma tarefa após timeout? | [Cenário de falha](../studies/scenarios/failure_reassignment/docker/scenario.py), eventos e [testes do executor](../runtime/services/orchestrator/internal/execution/executor_test.go) | Recuperação conforme retry e existência de alternativa |
| Políticas alteram a distribuição? | [Seleção de agentes, caso B](../studies/scenarios/agent_selection/benchmarks/run.py) | Três agentes com carga reportada configurada |
| O híbrido melhora propriedades do plano? | [Resultados logísticos](../studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2/logistics-summary.csv) | Mundo, dataset, modelo e amostra utilizados |
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

# campanha real em contêineres (credencial só nos contêineres LLM)
LOGISTICS_V3_DEMO=0 docker compose --env-file .env \
  -f studies/scenarios/logistics/v3/docker/compose.yaml up --build --wait -d
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

- [JSON de respostas e avaliações](../studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2/logistics-results.json)
- [Sumário CSV](../studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2/logistics-summary.csv)
- [Gráfico registrado](../studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2/logistics-quality.svg)
- [Eventos JSONL](../studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2/events.jsonl)
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
Os artefatos publicados permanecem intactos. Os runners abaixo foram ajustados
para a avaliação atual: não executam mais BDI isolado nem a comparação do caso E.

O caminho atual do estudo está em [studies/scenarios/logistics](../studies/scenarios/logistics/README.md):

```sh
ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/logistics/scenario.py
uv run --project sdk/python --extra llm python -m studies.scenarios.logistics.benchmarks.campaign
python3 -m studies.scenarios.logistics.evaluation.evaluate .ariadne/campaigns/logistics-ID
```

Os dois primeiros comandos usam o fluxo híbrido por padrão e fazem chamadas LLM.
O guia do estudo explica como selecionar LLM-only e exportar as credenciais. Substitua `logistics-ID`
pelo diretório informado na coleta. A avaliação usa os dados preservados nos
manifestos e escreve em uma pasta nova; não inicia agentes. No novo caminho,
todas as estratégias usam workflows, portanto os escopos de latência diferem
da campanha histórica. Consistência fica indefinida quando há uma só observação.

### Benchmarks por assunto

A antiga suíte A–D foi distribuída entre os cenários. Cada comando usa sua
própria topologia Docker e exporta resultados em `benchmarks/results/<data>/`:

```sh
sh studies/scenarios/basic_task/benchmarks/run.sh
sh studies/scenarios/agent_selection/benchmarks/run.sh
sh studies/scenarios/routing/benchmarks/run.sh
sh studies/scenarios/failure_reassignment/benchmarks/run.sh
LOGISTICS_REPETITIONS=2 sh studies/scenarios/logistics/benchmarks/run.sh
```

Todos exigem Docker/Compose, Python e uv. Apenas rotas (C) e logística exigem
acesso LLM: configure OPENAI_API_KEY e, opcionalmente, LLM_MODEL. Para logística,
crie `.env`; `BENCHMARK_ENV_FILE` permite selecionar outro arquivo. O antigo
caso E e BDI isolado não fazem parte da avaliação atual. C e D usam uma amostra.

As topologias usam a porta 54052 por padrão: execute uma por vez ou configure
BENCHMARK_ORCHESTRATOR_PORT. Os volumes são preservados e os eventos escritos
em append; salvar em pasta datada não isola eventos de campanhas anteriores.
Após preservar os dados anteriores, remova deliberadamente o volume da
respectiva topologia antes da nova coleta, por exemplo:

```sh
docker compose -f studies/scenarios/basic_task/benchmarks/compose.yaml down -v
```

Registre commit, configuração, versões e condições da máquina: os runners
Docker não produzem um manifesto completo. Para coletas com manifesto, use
as campanhas declarativas descritas acima.

## Interpretar e apresentar

Separe conclusão operacional, validade no domínio e conclusão de pesquisa.
Identifique a execução em cada tabela e gráfico. Preserve dados antigos ao
alterar critérios de medição e declare as [limitações](limitations.md).

[Índice](README.md)
