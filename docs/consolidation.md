# Organização, autoria e reprodução

O caminho principal é: declarar um experimento, coletar evidências pelo SDK e
runtime, avaliar essas evidências no estudo. Os exemplos Docker permanecem para
reprodução e demonstração das APIs de baixo nível.

## Organização

| Diretório | Responsabilidade |
|---|---|
| `proto/` | Contrato interoperável congelado |
| `runtime/` | Serviços Go |
| `sdk/python/` | Autoria, clientes, executor e coleta de campanhas |
| `examples/` | Experimentos curtos, incluindo BDI, LLM e agendamento |
| `examples/docker/` | Cenários de integração Docker |
| `examples/support/` | Agentes e cliente necessários aos exemplos Docker |
| `studies/logistics/` | Domínio, dados, experimentos e avaliação logística |
| `studies/benchmarks/` | Runners históricos e resultados preservados |
| `studies/runtime_metrics/` | Avaliação de eventos do runtime |
| `tools/` | Deploy, backend Docker, verificação e Inspector |
| `docs/` | Guias públicos |

Migração: `agents` e `clients` foram para `examples/support`; `scenarios` para
`examples/docker`; `benchmarks` para `studies/benchmarks`; `experiments` para
`studies/runtime_metrics`; `infra` para `tools/deploy`; scripts operacionais
para `tools`. Conteúdos das evidências históricas foram preservados. Caminhos
absolutos registrados dentro de evidências antigas continuam identificando a
coleta original; não são reescritos como se uma nova coleta tivesse ocorrido.

## Descrever e executar

`Scenario(agents=..., tasks=...)` contém apenas a descrição. Não abre canais,
não guarda resultados e não possui métodos de submissão. Para chamar um runtime
já iniciado, use `RuntimeClient(name, orchestrator_addr)`; ele oferece `submit`,
`submit_workflow`, `start_workflow`, `get_workflow`, `cancel_workflow` e contexto
`with`. Código antigo que usava `Scenario` como cliente deve trocar seu nome
para `RuntimeClient`. Os consumidores deste repositório já foram migrados.

BDI usa `Input` e `Plan`; veja [a referência](bdi.md). Para LLM, o caso simples
não precisa de classe de agente nem decorator:

```python
from pydantic import BaseModel
from tg_sdk import LlmAgent, Prompt

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
`examples/llm.py` não faz chamadas nem exige chave. O SDK mínimo instala apenas
gRPC e protobuf; o suporte LLM é um extra:

```sh
uv sync --project sdk/python --extra llm
TG_SDK_EXTRAS=llm ./tg check examples/llm.py
# Para executar, exporte OPENAI_API_KEY no terminal:
TG_SDK_EXTRAS=llm ./tg run examples/llm.py
```

Fora do checkout, instale `tg-sdk[llm]`. A descrição LLM usa Pydantic, portanto
requer o extra mesmo para `check`; credenciais são necessárias apenas na execução.

## Campanhas

Um arquivo de campanha aponta para um experimento e, opcionalmente, declara
uma matriz de variáveis de configuração:

```python
from tg_sdk import Campaign

campaign = Campaign(
    "../studies/logistics/experiment.py",
    matrix={"LOGISTICS_CASE": ["simple-delivery", "impossible-deadline"],
            "LOGISTICS_STRATEGY": ["bdi-only"]},
    repeat=2,
    name="logistics-check",
)
```

O caminho do experimento é relativo ao arquivo da campanha. Execute com
`./tg campaign arquivo.py --runtime-dir .tg/bin`. O exemplo
[examples/campaign.py](../examples/campaign.py) repete o echo com processos novos.
A matriz usa valores textuais e ordem de inserção; a repetição é o laço externo.
A coleta é sequencial, restaura o ambiente entre observações e cria uma execução
independente por combinação. Não use a matriz para credenciais: seus valores
são configuração pública e ficam registrados.

`campaign.json` registra o plano de coleta e cada observação antes de iniciá-la,
inclusive falhas de carregamento e cancelamento. Uma falha não impede as outras
observações; interrupção encerra a campanha. Cada execução tem seus próprios
logs. O comando específico `python -m studies.logistics.campaign` é um adaptador
para essa mesma implementação genérica. Avaliação e gráficos não entram no SDK.

## Proveniência

O `manifest.json` inclui revisão Git, estado modificado, versões dos pacotes,
hashes do arquivo principal, módulos Python carregados do repositório, arquivos
de dependências e binários. Declare dados externos com
`Scenario(artifacts=["world.json", "cases.json"])`, relativos ao experimento.
Arquivos declarados devem existir; arquivos `.env` não são aceitos.

A avaliação logística registra hashes dos manifestos/resultados usados e de
seus próprios módulos, além da revisão Git e versão de Python. Assim, uma
mudança de avaliador pode ser distinguida de uma nova execução dos agentes.
O avaliador continua funcionando com `python3 -S`, sem SDK instalado.

Proveniência identifica artefatos; não é um backup completo. Preserve a revisão,
os arquivos declarados e as dependências. Código importado dinamicamente só
no worker, dados não declarados e recursos externos mutáveis precisam de
registro específico do estudo. Estado Git modificado não torna a revisão, por
si só, suficiente para reconstruir o código.

## CLI e verificação

`./tg` é um bootstrap curto para a mesma CLI Python instalada como `tg`. Parsing,
status, logs, validação e execução estão no SDK. O backend Docker está isolado
em `tools/launcher/docker.sh`. Os comandos Docker e `verify` precisam do checkout;
configure `TG_ROOT` quando necessário. `TG_PYTHON` permite usar um Python com o
SDK já instalado; por padrão o bootstrap usa uv. `TG_SDK_EXTRAS=llm` inclui o extra.

`check` também detecta limite de etapas/profundidade, políticas desconhecidas e
parâmetros de retry inválidos antes de iniciar serviços. O Go continua sendo a
validação definitiva, inclusive para tamanhos e bindings materializados.

```sh
make verify
# Equivalente pelo comando público:
TG_SDK_EXTRAS=llm ./tg verify
```

A verificação inclui contrato, Go, SDK, integrações locais, logística com provedor
falso, launcher com Docker falso, métricas e Inspector. Também instala o SDK
mínimo em um ambiente separado e verifica que OpenAI/Pydantic não são dependências
obrigatórias. Requer Go, uv e Node; pode baixar dependências na primeira execução.
Não faz chamadas LLM reais nem precisa do daemon Docker. `--unit-only` omite
as integrações de processos; `--no-inspector` omite o visualizador.

A mesma rotina está em [.github/workflows/verify.yml](../.github/workflows/verify.yml).
Resultados de CI só existem depois que o workflow for executado pelo GitHub.

[Índice](README.md) · [Experimentos](experiments.md)
