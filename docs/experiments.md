# Experimentos declarativos em um arquivo

O arquivo Python descreve os agentes e o cenário. O SDK traduz as tarefas
para o contrato; o executor sobe serviços e agentes em contêineres e o runtime
Go realiza descoberta, seleção, workflows e recuperação. A avaliação consome os registros
depois da execução, em código separado.

## Primeiro experimento

No checkout, use Docker com Compose v2 e uv. A primeira execução prepara o
ambiente Python da CLI e constrói as imagens dos serviços Go e do agente
genérico; pode precisar baixar dependências.

O [estudo logístico](../studies/scenarios/logistics/README.md) usa essa mesma interface
para BDI, LLM e híbrido, com coleta e avaliação offline em comandos separados.

O exemplo completo [echo.py](../studies/scenarios/basic_task/scenario.py) contém:

```python
from ariadne_sdk import Agent, Scenario, Step

scenario = Scenario(
    agents=[Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})],
    tasks=[Step(capability="echo", goal="Olá, Ariadne!")],
)
```

Execute da raiz:

```sh
./ariadne check studies/scenarios/basic_task/scenario.py
./ariadne run studies/scenarios/basic_task/scenario.py
```

`check` importa o arquivo e verifica a descrição sem iniciar serviços. Declare
uma variável `scenario`. Mantenha no nível superior apenas definições e
configuração: o módulo é carregado pelo supervisor e novamente em cada processo
de agente. Código sob `if __name__ == "__main__"` não é executado pelo loader.

`run` sobe Registry, Orchestrator e Messaging em contêineres, mais um contêiner
por agente, todos num projeto Compose exclusivo da execução. O Docker escolhe
as portas publicadas no host. Os agentes são registrados depois que seus
endpoints estão prontos. Ao final, inclusive em falha ou Ctrl+C, o executor
remove os contêineres e preserva as evidências.

O resultado esperado termina com `WORKFLOW_STATUS_COMPLETED` e `Estado:
COMPLETED`. O terminal informa o diretório exclusivo em `studies/scenarios/basic_task/runs/ariadne-...`.
Sucesso significa conclusão operacional; critérios de domínio são avaliados
separadamente.

## Autoria de agentes

O handler recebe `Task` com `goal`, `payload`, `task_id`, `trace` e `attempt`.
Pode devolver um dicionário: o SDK monta o resultado com identidade, trace,
status e timestamps. Para metadados e falhas explícitas, devolva `TaskResult`.
Exceções são convertidas para os erros do contrato.

Classes que implementam `Agent.handle`, `BdiAgent` e `LlmAgent` usam o mesmo
executor. Veja [fixture de seleção BDI](../sdk/python/tests/fixtures/route_choice.py), que declara um agente BDI sem
subclasse, com dois planos e seleção de menor custo. A [referência BDI](bdi.md)
explica `Input`, `Plan`, `GoalPlan` e planejamento genérico; o [agendamento](../studies/scenarios/meeting/scenario.py)
aplica o ciclo de deliberação a agendas. Agentes maiores podem ser
importados de módulos instalados ou vizinhos ao arquivo do experimento.

Nomes/IDs de agentes devem ser únicos no cenário. A tarefa solicita uma
capacidade; o runtime escolhe entre os agentes que a oferecem. O executor
configura host (`agent-N`), porta e Registry de cada contêiner, sem depender
de `AGENT_PORT` ou `AGENT_ID` globais.

O executor não carrega `.env`. As variáveis que a descrição leu ao ser
carregada e as credenciais `OPENAI_API_KEY`, `OPENAI_BASE_URL` e `LLM_MODEL`
são repassadas por nome aos contêineres de agente quando existirem no
terminal. Para agentes LLM, exporte-as antes de executar. Os exemplos echo, BDI, workflow, recuperação e reunião não usam LLM.
`studies/scenarios/greeting/scenario.py` exige o extra `llm` e usa o provedor apenas na execução.

### LLM sem subclasse

Para LLM, o caso simples não precisa de classe de agente nem decorator:

```python
from pydantic import BaseModel
from ariadne_sdk import LlmAgent, Prompt

class Answer(BaseModel):
    text: str

agent = LlmAgent(
    name="answer", capabilities=["answer"], output_schema=Answer,
    prompt=lambda goal, payload: Prompt("Responda brevemente.", goal),
)
```

Para várias capacidades, use `handlers=[LlmCapability(nome, prompt, schema), ...]`.
O agente infere as capacidades anunciadas. `result_mapper` opcional adapta a
saída validada ao domínio. Prompts recebem `(goal, payload)`; podem também ser
um `Prompt` constante. Subclasses e `@llm_capability` continuam disponíveis.

O cliente OpenAI é criado na primeira execução, não na declaração. Validar
`studies/scenarios/greeting/scenario.py` não faz chamadas nem exige chave. O SDK
mínimo instala apenas gRPC e protobuf; o suporte LLM é um extra, necessário
mesmo para `check` porque a descrição usa Pydantic:

```sh
ARIADNE_SDK_EXTRAS=llm ./ariadne check studies/scenarios/greeting/scenario.py
export OPENAI_API_KEY=...
ARIADNE_SDK_EXTRAS=llm ./ariadne run studies/scenarios/greeting/scenario.py
```

`Scenario(agents=..., tasks=...)` contém apenas a descrição: não abre canais
nem guarda resultados. Para falar com um runtime já iniciado a partir de
código próprio, use `RuntimeClient(name, orchestrator_addr)`, que oferece
`submit`, `submit_workflow`, `start_workflow`, `get_workflow`,
`cancel_workflow`, `run_mission` e contexto `with`.

## Dependências entre tarefas

Em [workflow.py](../studies/scenarios/sequential_workflow/scenario.py), o segundo agente recebe o resultado
do primeiro:

```python
first = Step(capability="echo", goal="Olá, agentes!", name="first")
second = Step(
    capability="uppercase", goal="Transforme o texto em maiúsculas", name="second",
    payload={"text": first.output["text"]},
)
scenario = Scenario(agents=[echo, uppercase], tasks=[first, second])
```

`first.output["text"]` declara um binding e uma dependência no workflow Go.
`first.output` transfere o objeto inteiro. Campos aninhados são permitidos;
índices de arrays e referências dentro de arrays não são suportados pelo
compilador desta versão. Para ordenar tarefas sem transferir dados, use
`depends_on=(first,)`.

Etapas sem dependências podem rodar em paralelo. A ordem da lista não cria
dependências implícitas. A última etapa da lista determina o `output` final;
os resultados de todas as etapas são preservados. `Step` é a declaração;
`Task` é a entrada concreta recebida pelo agente durante a execução.

O runtime mantém seus limites atuais: até 10 etapas, profundidade 5,
paralelismo 4 e timeout global de workflow de 30 segundos. O comando `check`
verifica a descrição Python; a validação definitiva do contrato ocorre no Go.

## Falhas e repetição

```sh
./ariadne run studies/scenarios/sequential_workflow/scenario.py
./ariadne run studies/scenarios/failure_reassignment/scenario.py
./ariadne run studies/scenarios/basic_task/scenario.py --repeat 5
```

O exemplo de recuperação declara dois agentes com a mesma capacidade e uma
etapa com `deadline_ms=100`, `max_attempts=2` e `exclude_failed_agent=True`.
Os eventos Go mostram timeout e reassignment; os logs dos agentes mostram as
tentativas recebidas. Um agente pode terminar seu handler depois de o chamador
ter desistido; `caller_active` registra essa condição quando o handler retorna.
Timeout não garante cancelamento de efeitos externos.

`--repeat` executa o mesmo cenário sequencialmente, com novo trace e workflow
por amostra. Os contêineres e o estado interno dos agentes são reutilizados.
Para amostras com estado inicial independente, faça execuções separadas.
Falhas operacionais são preservadas e fazem o comando terminar com código 1;
interrupção termina com código 130. Uma falha de domínio devolvida como sucesso
pelo agente não é reinterpretada pelo executor.

`--ready-timeout 60` limita cada espera de prontidão e `--timeout 60` limita
o RPC de cada amostra. Esses parâmetros não ampliam o limite interno do
workflow. A construção das imagens tem limite de 30 minutos.

## Evidências e avaliação separada

Cada execução deixa uma pasta `ariadne-<id>/` em `runs/` ao lado do
`scenario.py`, com `manifest.json`, `summary.json`, `result.json`,
`results.jsonl`, `events.jsonl`, `mission-result.json` (missões) e a subpasta
`logs/`. A [referência do executor](cli.md#pasta-de-uma-execução) descreve cada
arquivo.

Correlacione agente e runtime por `task_id` e `trace_id`; distinga tentativas
por `attempt`. O diretório identifica a execução e `sample` identifica a
repetição. Entrada/saída e metadados fornecem os dados para avaliações externas,
inclusive métricas de domínio e tokens quando retornados pelo agente LLM.

As durações possuem escopos distintos: `client_duration_ms` cobre o RPC;
`duration_ms` no log do agente cobre o handler e sua adaptação; `elapsed_ms`
no resumo inclui o ciclo operacional. Nenhuma é, isoladamente, uma medição
controlada de overhead. A ferramenta não gera gráficos, CSV agregado ou
métricas de qualidade. Os runners históricos de benchmark continuam separados.

`Scenario(metadata={...})` permite preservar configuração de domínio no
manifesto. Esses dados não são injetados nos payloads dos agentes. A chave
`presentation` desse dicionário fornece título, descrição e rótulos de agentes
e passos ao [Mission Viewer](../tools/mission-viewer/README.md). Arquivos de
experimento podem pertencer a pacotes Python com `__init__.py`; o loader resolve
a raiz do pacote também ao executar fora do checkout.

O manifesto registra revisão Git, pacotes e hashes dos módulos carregados e
arquivos declarados com `Scenario(artifacts=[...])`. A avaliação também registra
sua proveniência. Isso identifica as entradas, mas não é um snapshot completo. Preserve esses artefatos e a revisão do código para uma
campanha acadêmica. Um processo encerrado à força pode ter entrada registrada
sem resultado; use os eventos de encerramento para interpretar esse caso.

## Campanhas

Um arquivo de campanha aponta para um experimento e, opcionalmente, declara
uma matriz de variáveis de configuração:

```python
from ariadne_sdk import Campaign

campaign = Campaign(
    "scenario.py",
    matrix={"LOGISTICS_V3_CASE": ["easy", "vehicle-loss"],
            "LOGISTICS_V3_CONFIGURATION": ["ariadne-v3", "single-llm-v3"]},
    repeat=2,
    name="logistics-v3-check",
)
```

O caminho do experimento é relativo ao arquivo da campanha. Execute com
`./ariadne campaign arquivo.py`; a campanha é gravada em `campaigns/campaign-<id>/`
ao lado do `scenario.py` (ou em `.ariadne/campaigns` para arquivos externos),
com `campaign.json` e um `runs/` com uma pasta de execução por observação. O exemplo
[basic_task/campaign.py](../studies/scenarios/basic_task/campaign.py)
repete o eco com uma topologia nova por observação. A matriz usa valores
textuais e ordem de inserção; a repetição é o laço externo. `timeout`
(segundos) limita o RPC de cada amostra, como `--timeout` em `run`; o padrão é
60 e `./ariadne campaign --timeout` o sobrepõe. A coleta é
sequencial, restaura o ambiente entre observações e cria uma execução
independente por combinação. Não use a matriz para credenciais: seus valores
são configuração pública e ficam registrados.

`campaign.json` registra o plano de coleta e cada observação antes de
iniciá-la, inclusive falhas de carregamento e cancelamento. Uma falha não
impede as outras observações; interrupção encerra a campanha. Avaliação e
gráficos não entram no SDK: cada estudo tem sua análise.

## Proveniência

O `manifest.json` inclui revisão Git, estado modificado, versões dos pacotes,
hashes do arquivo principal e dos módulos Python carregados do repositório,
arquivos de dependências, imagens usadas e variáveis repassadas por nome.
Declare dados externos com `Scenario(artifacts=["world.json", "cases.json"])`,
relativos ao experimento. Arquivos declarados devem existir; arquivos `.env`
não são aceitos.

A avaliação logística registra hashes dos manifestos/resultados usados e de
seus próprios módulos, além da revisão Git e versão de Python. Assim, uma
mudança de avaliador pode ser distinguida de uma nova execução dos agentes.

Proveniência identifica artefatos; não é um backup completo. Preserve a
revisão, os arquivos declarados e as dependências. Código importado
dinamicamente só no agente, dados não declarados e recursos externos mutáveis
precisam de registro específico do estudo.

## Onde o executor roda

`./ariadne run` precisa do checkout: as imagens dos serviços Go e do agente
genérico são construídas a partir de `runtime/` e `sdk/python/`, e o
repositório é montado nos contêineres para que os agentes importem seu código.
A CLI instalada como `ariadne` funciona da mesma forma quando `ARIADNE_ROOT`
aponta para um checkout. O arquivo do experimento pode estar fora do
repositório; sua pasta também é montada, somente leitura.

`--output /caminho/evidencias` muda a pasta que recebe diretórios de execução;
sem ela, cenários do repositório gravam em `runs/` ao lado do `scenario.py` e
arquivos externos em `.ariadne/runs`. `./ariadne status` e `./ariadne logs`
aceitam o ID ou o caminho da execução e, sem argumento, usam a última
execução iniciada. Os logs mostram as últimas 100 linhas de cada
arquivo `.log`/`.jsonl` e funcionam após o encerramento. Ctrl+C interrompe a
execução e remove os contêineres; `./ariadne stop ID` cobre o caso de uma
interrupção abrupta do processo.

[Índice](README.md) · [Desenvolvimento](development.md)


