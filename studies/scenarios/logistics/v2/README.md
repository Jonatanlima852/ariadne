# Logística v2

## Organização do código

| Caminho | Responsabilidade |
|---|---|
| `domain/` | Estado, contratos e regras do domínio |
| `execution/` | Controle dos episódios e variante enxuta |
| `agents/` | Especialistas, contratos de execução e Dockerfiles |
| `demonstrations/` | Substitutos determinísticos para integração |
| `datasets/` | Casos fixos das duas suítes |
| [benchmarks/](benchmarks/README.md) | Execução, arquivamento, análise e figuras |
| `docs/` | Guias de estresse, variante enxuta e apresentação |
| `tests/` | Verificações de estrutura e integração dos pacotes |
| `experiments/` | Protocolos congelados das coletas |
| [docker/](docker/README.md) | Topologia e instruções de execução |
| [results/](results/README.md) | Evidências selecionadas e material de apresentação |

Novas coletas ficam em `.ariadne/logistics-v2/`. Os caminhos dos resultados
preservados e os manifestos históricos permanecem como registrados na coleta.
Os guias [STRESS](docs/stress.md), [LEAN](docs/lean.md) e
[PRESENTATION](docs/presentation.md) detalham as variantes e a apresentação.

## Estudo

Comparação entre **Single LLM** e **Ariadne com dez especialistas**, no mesmo
mundo e com o mesmo modelo. A v1 permanece disponível no diretório superior.
Para a apresentação, comece pelo [roteiro e figuras prontos](docs/presentation.md).
A [confirmação do híbrido enxuto](results/stress-lean/README.md) contém 60
observações: tempo médio 17,8 vezes menor e 94,4% menos tokens nos 29 pares
com uso conhecido, com maior atendimento agregado.

Cada especialista tem seu próprio diretório `agents/<nome>/`, com declaração
em `main.py` e um `Dockerfile`. O [Compose](docker/compose.yaml) inicia um contêiner
por agente, além de Registry e Orchestrator. Single LLM possui seu próprio
contêiner. O controlador Python apenas envia tarefas pelo SDK; não instancia
agentes dentro de seu processo e não altera o núcleo do framework.

Da raiz, com Docker Compose e o SDK Python disponíveis:

```sh
# Serviços e agentes, cada um em seu contêiner:
LOGISTICS_V2_DEMO=0 docker compose --env-file .env \
  -f studies/scenarios/logistics/v2/docker/compose.yaml up --build --wait -d

# Conferir primeiro um caso pequeno com LLM real:
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run --cases easy

# Comparação dos dez casos:
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run

# Encerrar os contêineres deste cenário:
docker compose -f studies/scenarios/logistics/v2/docker/compose.yaml down
```

As credenciais são lidas pelo Compose no `--env-file .env` e ficam somente nos
contêineres LLM; o controlador não precisa de chave. Não são copiadas para imagens
ou evidências. O modelo vem de `LLM_MODEL` (padrão `gpt-5.6-luna`, como no SDK).
Para trocar o modelo, configure `LLM_MODEL` no ambiente e recrie os serviços.
O argumento `--model` do cliente verifica o modelo esperado dos agentes remotos;
ele não reconfigura um contêiner já iniciado.

Para a demonstração determinística, sem credenciais:

```sh
LOGISTICS_V2_DEMO=1 docker compose \
  -f studies/scenarios/logistics/v2/docker/compose.yaml up --build --wait -d
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run --demo
```

Essa execução é identificada como integração, sem benchmark de LLM. Para voltar
às chamadas reais, execute novamente o comando de subida com
`LOGISTICS_V2_DEMO=0` e `--env-file .env`. O cliente confere o modo dos agentes no
Registry e rejeita misturas entre demonstração e modelo real; confere também o
modelo informado nos resultados. Falhas do provedor não geram substituição
silenciosa por saídas determinísticas.

O cliente aceita `--orchestrator-addr` (padrão `localhost:55052`),
`--registry-addr` (padrão `localhost:55051`), `--max-rounds` (20), `--output`,
`--cases` e `--configurations single-llm ariadne`. As portas publicadas podem ser
alteradas por `LOGISTICS_V2_ORCHESTRATOR_PORT` e `LOGISTICS_V2_REGISTRY_PORT`.
Mais detalhes operacionais em [docker/README.md](docker/README.md).

A [configuração híbrida enxuta](docs/lean.md), `ariadne-lean`, mantém oito agentes
(um LLM e sete BDI) e preserva a equipe original como configuração separada.
Use `--configurations single-llm ariadne-lean` para compará-la ao baseline.
O Compose inclui também seu MissionCoordinator independente.

Cada configuração recebe uma cópia nova do mundo. Os casos são intercalados por
configuração, com uma observação por par. O estado do episódio fica no controlador;
os agentes recebem snapshots e devolvem propostas ou transições verificadas.
Os LLMs não editam o estado autoritativo. Os contêineres permanecem disponíveis
entre episódios; os agentes não guardam estado de domínio entre tarefas.

## Especialistas e cooperação

| Agente | Arquitetura | Decisão / capacidade registrada |
|---|---|---|
| OrderInterpreter | LLM | Extrai os pedidos naturais em requisitos; divergências dos pedidos reais encerram a execução com erro |
| MissionDecomposer | LLM | Ordena o atendimento e identifica dependências; recebe a análise de incidentes nas revisões |
| IncidentAnalyst | LLM | Identifica pedidos afetados e especialidades a rever, com base na ocorrência e no progresso |
| OperationsReporter | LLM | Explica decisões e resultados medidos, inclusive atendimento parcial |
| InventoryManager | BDI | Identifica depósitos com estoque ou cargas já em veículos |
| ResourceAllocator | BDI | Escolhe pedido, fonte e veículo disponível, considerando capacidade e acesso |
| RoutePlanner | BDI | Calcula conexões abertas até a fonte e o destino |
| EnergyManager | BDI | Seleciona plano direto ou busca uma rota com recarga e desvio |
| ConstraintSupervisor | BDI | Simula as ações propostas e aprova apenas um plano que efetivamente entregue |
| MissionExecutor | BDI | Aplica as mesmas transições do Single LLM; interrompe por incidente ou rejeição |

As capacidades têm o prefixo `logistics-v2-` e o nome do agente. Os seis BDI
usam `beliefs=Input('state')`, desejo do payload e seleção de `Plan` do SDK.
A escolha de energia tem dois planos: autonomia direta e busca com recarga.
A busca reutiliza `uniform_cost_search`; a adjacência reutiliza `_edges` do
domínio anterior. Nenhum BDI consulta um LLM.

Estoque → veículo → rota → energia → validação compõem um workflow Go com
bindings de resultados. As dependências reconhecidas do decompositor são
acrescentadas às dependências obrigatórias das regras. O executor é uma tarefa
separada. Essa divisão respeita o limite de profundidade do workflow existente
e evita colocar chamadas LLM num workflow global limitado a 30 segundos.

Trocar a fonte muda a rota. Falta de autonomia aciona busca com recarga;
se não existir solução, a escolha rejeitada é excluída da próxima alocação.
Uma pane permite recuperar carga com outro veículo no mesmo local. Um bloqueio
faz o executor parar e o analista alimentar uma nova decomposição. A análise
não pode dispensar validação: as etapas BDI são refeitas com o estado atualizado.
O IncidentAnalyst só é chamado se existe ocorrência ou motivo de revisão;
o decompositor não é chamado novamente após cada entrega normal.

Single LLM decide suas próprias sequências de ações e pode combinar pedidos.
Recebe o mundo completo, pedidos, regras, ocorrências observadas e feedback.
As ações são aplicadas diretamente pelo domínio; não recebe reparo simbólico.
Após erro ou incidente, recebe o estado atualizado e pode revisar seu plano.
Na demonstração `--demo`, **ambos** os lados usam substitutos que reaproveitam
políticas simbólicas; isso confere integração e não mede capacidade de LLM.

## Regras e limites

O mapa A–H, energias, durações e recarga vêm do domínio existente. As arestas são bidirecionais por padrão, como na v1; isso é
explicitado também no prompt. Os campos
de pacote único, chave e porta da v1 não fazem parte do contrato da v2; todos
os movimentos dependem das conexões e bloqueios do episódio. Cada aresta tem
uma distância explícita, numericamente igual aos minutos do mapa herdado.

Pedidos têm itens, destino, prioridade (maior primeiro) e prazo absoluto.
Cada pedido é atendido inteiro por um depósito; não há divisão de estoque
entre depósitos. Capacidade é a soma dos pesos dos itens. `LOAD` consome estoque,
`MOVE` consome bateria, `RECHARGE` exige carregador e `DELIVER` exige a carga
completa no destino. `TRANSFER` recupera carga de veículo indisponível no mesmo
local. A carga indisponível permanece fisicamente no veículo até a recuperação.

As transições validam antes de modificar o estado e registram ações aceitas e
rejeitadas. Somente `DELIVER` aceito escreve no registro de entregas. Prazos são
flexíveis: uma entrega atrasada continua sendo entrega, mas não conta como feita
no prazo. O tempo simulado é global e sequencial, sem condução paralela de veículos.
A seleção é uma heurística local, sem alegação de otimalidade global.

Incidentes são disparados **antes da próxima ação**, após o limiar de ações
aceitas em `after_actions`; rejeições não avançam o limiar. As duas configurações
usam a mesma programação, mas os LLMs só recebem os eventos quando ocorrem.
Podem estar em locais diferentes quando um evento dispara. Um incidente após a última ação do episódio não é disparado, pois não
há próxima ação. O executor interrompe o restante do plano ao disparar um evento.

Cada episódio tem no máximo 20 rodadas; cada proposta executa no máximo 200 ações.
Uma proposta maior é truncada e o próximo turno recebe o progresso. Não há
repetição automática de tarefas ou chamadas do provedor. A chamada ao provedor
tem limite de 90 segundos; a tarefa LLM tem prazo de 120 segundos.
O limite de busca é 10.000 expansões: esgotá-lo é erro operacional, não prova
de impossibilidade. Estes limites mantêm a execução finita.

## Casos, métricas e evidências

A [suíte de estresse](docs/stress.md), em [datasets/stress.json](datasets/stress.json),
acrescenta dez casos fixos com 6–10 pedidos, 16 locais, quatro veículos,
itens compostos, mãos únicas e incidentes sucessivos. Use `--suite stress`;
`--suite basic` mantém os casos originais, e `--suite all` executa ambos.
`--repeat N` repete os mesmos casos com estados novos e alterna a ordem das
configurações entre repetições. Não seleciona casos conforme o vencedor.


[datasets/basic.json](datasets/basic.json) contém dez episódios completos e fixos, com pedidos
naturais e seus requisitos autoritativos. Cobre recursos suficientes, estoque
concorrido, veículo único, recarga, prioridades/prazos, bloqueio, pane, capacidade
insuficiente e incidentes combinados. `expected` documenta resultados conhecidos;
não é enviado aos agentes nem usado para fabricar métricas.
A coerência estrutural dos dez casos é conferida antes de executar os episódios.

Cada execução grava em `.ariadne/logistics-v2/<id>/`:

- `results.json`: métricas, estado final, histórico de ações/ocorrências, chamadas e workflows;
- `comparison.md`: tabela das duas configurações por caso;
- `manifest.json`: casos, modelo, limites, hashes das fontes e declarações registradas dos agentes;
- os eventos do Orchestrator ficam no volume `events_data` do Compose; os logs são consultados com `docker compose logs`. Os IDs de trace dos resultados permitem correlacionar as tarefas.

Entregues, entregas no prazo, rejeições, distância e energia de movimento são calculados
somente do estado e histórico. Rejeições de propostas durante a simulação do
supervisor não contam como ações executadas/rejeitadas no mundo. `wall_seconds`
mede o episódio, incluindo interpretação, análise e relatório; exclui inicialização
e encerramento dos contêineres. Chamadas contam invocações LLM, incluindo
resultados de falha; tokens vêm do provedor. Tokens indisponíveis são `null`,
inclusive na demonstração. Falhas antes de retornar uso podem não ter tokens
contabilizados. Não calculamos preço monetário.

Os resultados preservados estão em [results](results/README.md).
Para visualizá-los, abra `./ariadne inspect` e selecione **Logística v2**.
A mesma aba lista as coletas em `.ariadne/logistics-v2`, com comparação por caso,
gráficos, histórico de ações e incidentes, prazos e consumo por agente.
A interface apenas lê as evidências; não inicia episódios nem chama modelos.
Uma única observação por caso não sustenta conclusões estatísticas. A coleta é local,
sequencial e sem controle de aquecimento do provedor. A validação original foi feita executando o fluxo real e a demonstração de
integração, incluindo recarga, incidentes e recuperação de carga. Após a
organização dos pacotes, `tests/test_integration.py` acrescenta verificações de
carregamento das suítes, declaração dos agentes sem credenciais e integração
entre proposta de demonstração, schema e transições. Essas verificações fazem
parte de `make verify` e não medem qualidade de LLM.
