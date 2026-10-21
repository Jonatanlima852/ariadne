# Primeira execução

O caminho recomendado usa um experimento Python e processos locais. Não exige
Docker, protoc ou chave de LLM. Execute os comandos na raiz do repositório.

## 1. Preparar e conferir

Instale Go compatível com `runtime/go.mod` (atualmente >=1.26.3) e uv.
Use macOS/Linux ou WSL. O uv prepara o Python e o SDK; a primeira execução pode
baixar dependências. O projeto seleciona Python pela configuração do SDK.

```sh
./ariadne doctor --local --file examples/echo.py
```

Todas as linhas devem começar com `OK`. O diagnóstico confere Python, SDK,
Go, destino de evidências e a descrição do exemplo. Não compila nem inicia
serviços; o bootstrap uv pode preparar o ambiente antes do diagnóstico.

## 2. Executar

```sh
./ariadne run examples/echo.py
```

O executor compila o runtime com cache, inicia os serviços Go e o agente Python,
espera a prontidão e executa o workflow. Ao terminar, encerra seus processos e
preserva os resultados. O terminal deve mostrar:

```text
Amostra 1/1: WORKFLOW_STATUS_COMPLETED
Resultado: {"text": "Olá, Ariadne!"}
Estado: COMPLETED
Evidências: .../.ariadne/runs/ariadne-.../
```

A tarefa pede a capacidade `echo`; o runtime descobre o agente e recebe sua
resposta. `COMPLETED` indica conclusão operacional, não uma avaliação científica.

## 3. Consultar o resultado

```sh
./ariadne status
./ariadne logs
```

Sem argumento, consultam a última execução. Os logs continuam disponíveis após
o encerramento. `result.json` contém a resposta; `events.jsonl` registra eventos;
`manifest.json` descreve o experimento. Para interromper uma execução local,
use Ctrl+C no terminal do executor.

## 4. Abrir a visualização

Esta etapa é opcional e exige Node **22.12 ou superior** na linha 22 (usada no CI),
npm e uv. O intervalo aceito pelo frontend é `^20.19.0 || >=22.12.0`.

```sh
./ariadne doctor --local --inspector
./ariadne inspect
```

Abra `http://127.0.0.1:4173`, escolha a execução e consulte **Etapas** e
**Workflow e replay**. O comando prepara as dependências do frontend quando
necessário, inicia API e interface e aguarda ambas ficarem prontas. Ctrl+C
encerra os dois processos. A interface lê arquivos salvos; não precisa dos
agentes ativos. Na aba **Demonstrações**, há registros para explorar sem nova coleta.
O [guia do Inspector](../tools/inspector/README.md) explica outras opções.

## 5. Explorar cooperação e recuperação

```sh
./ariadne run examples/workflow.py
./ariadne run examples/recovery.py
./ariadne run studies/logistics/experiment.py
```

O primeiro exemplo transfere a saída entre etapas; o segundo demonstra timeout
e reassignment; o terceiro planeja uma missão logística com BDI. Todos dispensam
LLM. Consulte [experimentos](experiments.md) e [o estudo logístico](../studies/logistics/README.md).

## Alternativa com Docker

Com uv e Docker Compose >=2.24.4, é possível executar a demonstração básica sem
Go no host. A CLI usa Python preparado pelo uv; os serviços e o cliente da tarefa
rodam em contêineres.

```sh
./ariadne doctor
./ariadne demo
./ariadne status
./ariadne logs
```

A resposta esperada identifica `mock-agent-01` e `Estado: COMPLETED`.
O launcher encerra sua topologia automaticamente. Para manter os serviços,
use `./ariadne demo --keep` e depois `./ariadne stop`.
Veja [cenários Docker](scenarios.md), [referência da CLI](cli.md) e
[execução manual](manual-execution.md) para publicar portas ou controlar Compose.

## Diagnóstico rápido

| Situação | Próximo passo |
|---|---|
| uv ausente | Instale uv ou configure `ARIADNE_PYTHON` com um Python que tenha o SDK |
| Go ausente ou antigo | Confira `runtime/go.mod` e repita `doctor --local` |
| Falha de build | Leia `build.log` na pasta informada; confira rede e dependências |
| Processo ou agente não iniciou | Leia `summary.json` e os arquivos `.log` via `./ariadne logs` |
| Inspector não abre | Rode `doctor --local --inspector`; confira os dois terminais e a porta 4173 |
| Docker indisponível | Inicie Docker e execute `./ariadne doctor` |

[Índice](README.md)
