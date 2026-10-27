# Híbrido enxuto: revisão da divisão de trabalho

`ariadne-lean` é uma configuração experimental separada da equipe original
`ariadne`. A versão original, suas perdas e os resultados anteriores são
preservados. A nova versão usa oito agentes independentes, cada um com seu
próprio processo e contêiner:

| Agente | Arquitetura | Responsabilidade |
|---|---|---|
| OrderInterpreter | LLM | Interpretar os pedidos naturais, conferidos contra os requisitos autoritativos |
| MissionCoordinator | BDI | Ordenar trabalho pendente e revisar a missão a partir das crenças atuais |
| InventoryManager | BDI | Localizar estoque ou carga já embarcada |
| ResourceAllocator | BDI | Escolher fonte e veículo compatíveis |
| RoutePlanner | BDI | Encontrar conexões abertas |
| EnergyManager | BDI | Planejar recarga e preservar acesso posterior a um carregador |
| ConstraintSupervisor | BDI | Validar efeitos concretos antes da execução |
| MissionExecutor | BDI | Aplicar ações e interromper por incidente ou rejeição |

O runtime continua descobrindo capacidades e encaminhando tarefas e resultados.
Os bindings do workflow carregam estoque → alocação → rota → energia → validação.
O executor é acionado separadamente. Os agentes não trocam mensagens diretamente.

## Por que revisar a equipe

Na versão original, falhas de viabilidade durante o planejamento acionavam
novamente IncidentAnalyst e MissionDecomposer, ambos LLM. Isso acontecia mesmo
quando não havia um novo incidente no mundo. Em s06, foram 21 chamadas LLM.
OperationsReporter também acrescentava uma chamada ao caminho crítico e podia
introduzir afirmações incorretas no relato final.

A configuração enxuta deixa a interpretação linguística com o LLM e transfere
coordenação e revisão para um plano BDI explícito. O resumo final é calculado
das métricas. Não há substituição silenciosa de respostas LLM por fixtures.

A política energética original entregava um pedido mesmo quando o veículo
terminava sem bateria para voltar a um carregador. Em s04, três veículos ficaram
com 0, 1 e 2 unidades de bateria em locais sem carregador. A nova política requer
energia para alcançar um carregador após a entrega enquanto houver trabalho
pendente. Isso pode aumentar distância e consumo para preservar atendimento;
não é uma otimização global de rotas.

## Comparação fixada antes da confirmação

O [protocolo congelado](../experiments/lean-v1-confirmation.json) prevê os dez casos
de estresse, três repetições e as configurações `single-llm` e `ariadne-lean`:
60 observações. Cada repetição cria estados novos; a ordem das configurações é
invertida na segunda repetição. O modelo, os requisitos, as transições, os
incidentes e os limites permanecem iguais. O prompt do Single LLM foi preservado;
ele pode combinar vários pedidos e revisar suas ações.

Os dois lados recebem as mesmas regras e o mesmo mundo. O híbrido tem acesso aos
planejadores simbólicos que compõem a arquitetura investigada. O Single LLM
decide suas ações sem esse serviço. O orçamento de chamadas efetivamente usado
é uma métrica, não um limite artificialmente imposto ao baseline.

O desenvolvimento utilizou resultados desta suíte. As três repetições avaliam
variação nos mesmos casos; não são um teste de generalização para mundos inéditos.
As mudanças incluem tanto composição de agentes quanto política energética.
A comparação não isola o efeito causal do runtime, nem sustenta que adicionar
mais agentes sempre melhora uma solução. O Single LLM gera sequências completas
no contrato estruturado de ações; o híbrido gera requisitos e planeja as ações
em código. A diferença de volume de saída faz parte do custo observado desta
divisão de trabalho, sem provar uma superioridade intrínseca de raciocínio.
Um baseline com contrato mais compacto seria outra comparação.

O limite de 90 segundos por chamada vale para os dois lados. Timeouts continuam
como erros operacionais nas métricas de atendimento e tempo. Quando não há uso
de tokens retornado, o valor permanece ausente; comparações agregadas de tokens
utilizam apenas pares com uso conhecido nos dois lados e informam essa cobertura.

```sh
LOGISTICS_V2_DEMO=0 docker compose --env-file .env \
  -f studies/scenarios/logistics/v2/docker/compose.yaml up --build --wait -d

uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.run \
  --suite stress --repeat 3 --configurations single-llm ariadne-lean
```

Preserve uma coleta concluída com replay de seus estados:

```sh
uv run --project sdk/python python -m studies.scenarios.logistics.v2.benchmarks.archive \
  --name stress-lean .ariadne/logistics-v2/ID
```

O arquivador rejeita observações duplicadas, mundos diferentes com o mesmo ID e
misturas de modelo, suíte ou modo de execução. Uma coleta cancelada só é aceita
com `--allow-incomplete` e permanece identificada como incompleta.

As [figuras de circulação das tarefas](../results/presentation/README.md) e a aba
**Logística v2** do Inspector mostram o percurso observado na equipe original
e na configuração enxuta. Os [resultados da confirmação](../results/stress-lean/README.md)
foram preservados separadamente dos pilotos e da demonstração determinística:
60 observações, tempo médio 17,8 vezes menor, 94,4% menos tokens nos 29 pares
com uso conhecido e 219/228 contra 204/228 pedidos entregues. O relatório mantém
o timeout, os casos desfavoráveis e a análise sem o par do timeout.
