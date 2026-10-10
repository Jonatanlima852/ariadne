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
3. Observe [workflow](../scenarios/workflow-sequential/README.md) e
   [reassignment](../scenarios/failure-reassignment/README.md) sem LLM.
4. Execute a [rota heterogênea](../scenarios/heterogeneous-route/README.md),
   caso haja credencial e acesso ao provedor.
5. Consulte os resultados logísticos já registrados e suas limitações.

Ler os artefatos selecionados não exige Docker nem chamadas externas. Uma nova
coleta LLM é uma nova observação: não se espera igualdade exata de latências e
respostas com a execução publicada.

## Perguntas e evidências

| Pergunta | Onde conferir | Alcance |
|---|---|---|
| Agentes heterogêneos cooperam pelo contrato? | [Cenário de rota](../examples/demo_scenario/heterogeneous_demo.py) e [contrato](../proto/contract/v1/contract.proto) | Agentes BDI-like e LLM utilizados nos exemplos |
| O runtime recupera uma tarefa após timeout? | [Cenário de falha](../scenarios/failure-reassignment/scenario.py), eventos e [testes do executor](../runtime/services/orchestrator/internal/execution/executor_test.go) | Recuperação conforme retry e existência de alternativa |
| Políticas alteram a distribuição? | Caso B do [runner A–E](../benchmarks/run.py) | Três agentes com carga reportada configurada |
| O híbrido melhora propriedades do plano? | [Resultados logísticos](../benchmarks/results/logistics-20261004T-final-v2/logistics-summary.csv) | Mundo, dataset, modelo e amostra utilizados |
| Qual é o overhead do runtime? | Requer comparação controlada da mesma tarefa com e sem runtime | O caso E compara fluxos diferentes e não isola esse custo |

Os testes automatizados verificam comportamentos específicos. Eles não
substituem uma avaliação experimental nem provam generalidade dos resultados.

## Resultados logísticos selecionados

Execução `logistics-20261004T-final-v2`, registrada em 4 de outubro de 2026:
oito casos, duas repetições e 16 respostas por estratégia, com modelo
`gpt-5.6-luna`. As estratégias são:

- BDI-only: recebe a missão estruturada e usa planejamento simbólico.
- LLM-only: recebe pedido natural e mundo e propõe uma sequência de ações.
- Híbrido: LLM interpreta restrições; BDI planeja a missão estruturada.

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

- [JSON de respostas e avaliações](../benchmarks/results/logistics-20261004T-final-v2/logistics-results.json)
- [Sumário CSV](../benchmarks/results/logistics-20261004T-final-v2/logistics-summary.csv)
- [Gráfico registrado](../benchmarks/results/logistics-20261004T-final-v2/logistics-quality.svg)
- [Eventos JSONL](../benchmarks/results/logistics-20261004T-final-v2/events.jsonl)
- [Mundo](../studies/logistics/world.json), [casos](../studies/logistics/cases.json) e [avaliador](../studies/logistics/domain.py)

O avaliador compartilha regras e o planejador de referência com o agente BDI.
Além disso, no caminho de plano executável, `safe` exige que o estado final
satisfaça o objetivo; não mede exclusivamente a aplicabilidade das transições.
Essas convenções devem acompanhar qualquer uso das métricas publicadas.

## Executar uma nova campanha

Na interface declarativa, `./tg run arquivo.py --repeat N` preserva as amostras
brutas e logs correlacionados. A avaliação e os gráficos são feitos depois,
em código separado. O [guia de experimentos](experiments.md) descreve os
arquivos, os escopos de duração e a reutilização de estado entre repetições.
Os runners históricos abaixo mantêm seu comportamento e artefatos publicados.

O caminho atual do estudo está em [studies/logistics](../studies/logistics/README.md):

```sh
./tg run studies/logistics/experiment.py
uv run --project sdk/python python -m studies.logistics.campaign
python3 -m studies.logistics.evaluate .tg/campaigns/logistics-ID
```

Os dois primeiros comandos usam BDI por padrão. O guia do estudo explica
como selecionar LLM/híbrido e exportar as credenciais. Substitua `logistics-ID`
pelo diretório informado na coleta. A avaliação usa os dados preservados nos
manifestos e escreve em uma pasta nova; não inicia agentes. No novo caminho,
todas as estratégias usam workflows, portanto os escopos de latência diferem
da campanha histórica. Consistência fica indefinida quando há uma só observação.

### Runners históricos

Os cenários de demonstração podem ser executados via `./tg scenario NOME`,
com dados isolados em `.tg/runs/`. Os comandos abaixo continuam usando os
runners específicos de benchmark, com os requisitos e limitações próprios.

Requisitos: Docker/Compose, Python, uv e acesso ao modelo configurado. Crie
`.env` na raiz com `OPENAI_API_KEY` e, se necessário, `LLM_MODEL`. A chave deve
permanecer local. Os scripts aceitam outro arquivo via `BENCHMARK_ENV_FILE`.

```sh
./benchmarks/run.sh
```

A suíte A–E mede execução básica, políticas, cooperação heterogênea,
recuperação e comparação de entrada estruturada com fluxo assistido por LLM.
Os casos C, D e E têm uma amostra por execução padrão.

```sh
LOGISTICS_REPETITIONS=2 ./benchmarks/run-logistics.sh
```

O segundo comando executa a comparação logística. Ambos usam
`benchmarks/compose.yaml`, porta 54052 por padrão, criam uma pasta de resultados
datada e encerram os contêineres ao sair.

### Isolar os eventos antes de medir

Os runners preservam o volume entre execuções e o logger escreve em modo
append. Portanto, a pasta datada não garante, sozinha, que o JSONL copiado
contenha apenas a campanha atual. Não execute os dois runners simultaneamente.

Após salvar dados anteriores e encerrar qualquer uso dessa topologia, uma
limpeza deliberada do volume pode ser feita antes de uma campanha:

```sh
docker compose --env-file .env -f benchmarks/compose.yaml down -v
```

Esse comando apaga o volume da topologia de benchmarks. Para avaliação,
registre também commit, configuração, versões e condições da máquina: o runner
atual não produz um manifesto completo dessas informações.

## Interpretar e apresentar

Separe conclusão operacional, validade no domínio e conclusão de pesquisa.
Identifique a execução em cada tabela e gráfico. Preserve dados antigos ao
alterar critérios de medição e declare as [limitações](limitations.md).

[Índice](README.md)
