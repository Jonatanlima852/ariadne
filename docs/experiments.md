# Experimentos declarativos em um arquivo

O arquivo Python descreve os agentes e o cenário. O SDK traduz as tarefas
para o contrato; o executor inicia processos locais e o runtime Go realiza
descoberta, seleção, workflows e recuperação. A avaliação consome os registros
depois da execução, em código separado.

## Primeiro experimento

No checkout, use Go compatível com `runtime/go.mod` e uv. Não é necessário
Docker neste caminho. A primeira execução prepara o ambiente Python do SDK
e compila os serviços Go; pode precisar baixar dependências.

O [estudo logístico](../studies/logistics/README.md) usa essa mesma interface
para BDI, LLM e híbrido, com coleta e avaliação offline em comandos separados.

O exemplo completo [echo.py](../examples/echo.py) contém:

```python
from tg_sdk import Agent, Scenario, Step

scenario = Scenario(
    agents=[Agent(name="echo", capabilities=["echo"], handler=lambda task: {"text": task.goal})],
    tasks=[Step(capability="echo", goal="Olá, TG!")],
)
```

Execute da raiz:

```sh
./tg check examples/echo.py
./tg run examples/echo.py
```

`check` importa o arquivo e verifica a descrição sem iniciar serviços. Declare
uma variável `scenario`. Mantenha no nível superior apenas definições e
configuração: o módulo é carregado pelo supervisor e novamente em cada processo
de agente. Código sob `if __name__ == "__main__"` não é executado pelo loader.

`run` inicia Registry, Orchestrator e Messaging em processos Go, mais um processo
Python por agente. O sistema operacional escolhe portas livres. Os agentes são
registrados depois que seus endpoints estão prontos. Ao final, inclusive em
falha ou Ctrl+C, o executor encerra os processos e preserva as evidências.

O resultado esperado termina com `WORKFLOW_STATUS_COMPLETED` e `Estado:
COMPLETED`. O terminal informa o diretório exclusivo em `.tg/runs/tg-...`.
Sucesso significa conclusão operacional; critérios de domínio são avaliados
separadamente.

## Autoria de agentes

O handler recebe `Task` com `goal`, `payload`, `task_id`, `trace` e `attempt`.
Pode devolver um dicionário: o SDK monta o resultado com identidade, trace,
status e timestamps. Para metadados e falhas explícitas, devolva `TaskResult`.
Exceções são convertidas para os erros do contrato.

Classes que implementam `Agent.handle`, `BdiAgent` e `LlmAgent` usam o mesmo
executor. Veja [bdi.py](../examples/bdi.py), que declara um agente BDI sem
subclasse, com dois planos e seleção de menor custo. A [referência BDI](bdi.md)
explica `Input`, `Plan` e planejamento genérico; [meeting.py](../examples/meeting.py)
aplica a mesma interface a agendas. Agentes maiores podem ser
importados de módulos instalados ou vizinhos ao arquivo do experimento.

Nomes/IDs de agentes devem ser únicos no cenário. A tarefa solicita uma
capacidade; o runtime escolhe entre os agentes que a oferecem. O backend local
configura host, porta e Registry automaticamente, sem depender de `AGENT_PORT`
ou `AGENT_ID` globais.

O backend local herda o ambiente do terminal e não carrega `.env`
automaticamente. Para agentes LLM, exporte as variáveis necessárias, incluindo
`OPENAI_API_KEY`, antes de executar. Os exemplos echo, BDI, workflow, recuperação e reunião não usam LLM.
`examples/llm.py` exige o extra `llm` e usa o provedor apenas na execução.

## Dependências entre tarefas

Em [workflow.py](../examples/workflow.py), o segundo agente recebe o resultado
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
./tg run examples/workflow.py
./tg run examples/recovery.py
./tg run examples/bdi.py
./tg run examples/echo.py --repeat 5
```

O exemplo de recuperação declara dois agentes com a mesma capacidade e uma
etapa com `deadline_ms=100`, `max_attempts=2` e `exclude_failed_agent=True`.
Os eventos Go mostram timeout e reassignment; os logs dos agentes mostram as
tentativas recebidas. Um agente pode terminar seu handler depois de o chamador
ter desistido; `caller_active` registra essa condição quando o handler retorna.
Timeout não garante cancelamento de efeitos externos.

`--repeat` executa o mesmo cenário sequencialmente, com novo trace e workflow
por amostra. Os processos e o estado interno dos agentes são reutilizados.
Para amostras com estado inicial independente, faça execuções separadas.
Falhas operacionais são preservadas e fazem o comando terminar com código 1;
interrupção termina com código 130. Uma falha de domínio devolvida como sucesso
pelo agente não é reinterpretada pelo executor.

`--ready-timeout 30` limita cada espera de prontidão e `--timeout 60` limita
o RPC de cada amostra. Esses parâmetros não ampliam o limite interno do
workflow. O preparo dos binários tem limite de 300 segundos por serviço.

## Evidências e avaliação separada

| Arquivo | Conteúdo |
|---|---|
| `manifest.json` | Descrição compilada, agentes, versão de schema, hash do arquivo e binários, ambiente e endereços |
| `experiment.py` | Cópia da descrição executada |
| `execution.jsonl` | Ciclo do executor, processos e amostras, com interrupções e encerramentos forçados |
| `events.jsonl` | Eventos de tarefas e workflows emitidos pelo Orchestrator |
| `message-events.jsonl` | Eventos do broker, se houver mensagens |
| `agent-N.jsonl` | Entrada e resultado completo de cada tentativa, trace, duração do handler e eventos do agente |
| `agent-N.log` | Logging e stdout/stderr do processo do agente |
| `registry.log`, `orchestrator.log`, `messaging.log` | Logs JSON dos serviços Go |
| `results.jsonl` | Uma resposta por amostra, incluindo falhas de RPC |
| `result.json` | Resposta da última amostra concluída, para inspeção rápida |
| `summary.json`, `status`, `environment` | Estado e duração operacional, incluindo preparo e encerramento |
| `build.log` | Saída da compilação, quando solicitada |

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
manifesto. Esses dados não são injetados nos payloads dos agentes. Arquivos de
experimento podem pertencer a pacotes Python com `__init__.py`; o loader resolve
a raiz do pacote também ao executar fora do checkout.

O manifesto registra revisão Git, pacotes e hashes dos módulos carregados e
arquivos declarados com `Scenario(artifacts=[...])`. A avaliação também registra
sua proveniência. Isso identifica as entradas, mas não é um snapshot completo. Preserve esses artefatos e a revisão do código para uma
campanha acadêmica. Um processo encerrado à força pode ter entrada registrada
sem resultado; use os eventos de encerramento para interpretar esse caso.

## Uso fora do checkout

Com o SDK instalado no ambiente Python e os binários preparados:

```sh
tg run /caminho/meu_experimento.py --runtime-dir /caminho/binarios
```

O diretório precisa conter `tg-registry`, `tg-orchestrator` e `tg-messaging`.
`TG_RUNTIME_DIR` também configura esse caminho. No checkout, `./tg run` prepara
os binários em `.tg/bin` e usa o cache Go. `--runtime-dir` evita a compilação.
`--output /caminho/evidencias` muda a pasta que recebe diretórios de execução.

Esta versão oferece o backend de processos locais. Não conecta a execução
declarativa a um cluster externo nem gera contêineres; os fluxos Docker antigos
continuam disponíveis. `./tg status` e `./tg logs` reconhecem ambos os backends,
por ID ou caminho da execução. Sem argumento, usam a última execução iniciada
no diretório compartilhado. Para processos locais, logs mostram as últimas
100 linhas de cada arquivo `.log`/`.jsonl` e funcionam após o encerramento.
`stop` continua controlando Docker; para interromper processos locais, use
Ctrl+C no supervisor.

O shell usa `.tg/runs` deste checkout mesmo quando invocado de outro diretório.
`TG_RUNS_DIR` muda essa raiz. Para uma execução com `--output` personalizado,
passe seu caminho a `status`/`logs` ou configure a mesma raiz. A CLI instalada
também oferece `tg status --output PASTA` e `tg logs --output PASTA --tail 50`,
com consulta offline das evidências salvas de ambos os backends.
O Inspector pode listar o resultado de workflow salvo; a exploração dos logs
por agente e das repetições usa os arquivos brutos.

[Índice](README.md) · [Desenvolvimento](development.md)

Consulte [consolidação](consolidation.md) para LLM declarativo, `RuntimeClient`,
`Campaign`, dependências opcionais e a verificação integrada.
