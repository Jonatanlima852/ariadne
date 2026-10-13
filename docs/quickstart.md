# Primeira execução

`./tg` prepara uma topologia isolada, espera pelos serviços e agentes, executa
a demonstração e salva os resultados antes de encerrar o ambiente.

## Requisitos

- Repositório clonado e terminal na raiz.
- uv (ou `TG_PYTHON` apontando para um Python com o SDK instalado).
- Docker em execução, com Docker Compose **2.24.4 ou superior**.
- Shell POSIX: macOS/Linux; no Windows, use um ambiente como WSL com Docker.
- Rede para baixar imagens e dependências na primeira construção.

O cliente da tarefa roda em contêiner. A CLI única usa Python pelo uv, que pode
preparar esse ambiente na primeira execução. Go e protoc não são necessários
no host para esta demonstração Docker, nem uma chave LLM.

## 1. Conferir o ambiente

```sh
./tg doctor
```

O diagnóstico verifica Docker, versão do Compose e configuração da topologia,
sem iniciar contêineres. O executor não publica portas no host: pode coexistir
com outras topologias sem disputar as portas 50051/50052.

## 2. Executar a demonstração

```sh
./tg demo
```

A primeira construção pode demorar. O comando informa o caminho de `build.log`
e avança por prontidão, execução e validação. O trecho final deve conter:

```text
Cenário aprovado: demo
Estado: COMPLETED
Resultados: .../.tg/runs/tg-.../
```

A tarefa solicita a capacidade `echo`, o Orchestrator descobre `mock-agent-01`
e o agente conclui a tarefa. O mock atual devolve status e identificação; esta
demonstração não exige um payload de resposta. O resultado completo e seu
trace ficam em `result.json`.

## 3. Consultar o resultado

```sh
./tg status
./tg logs
```

Os comandos usam a última execução iniciada neste checkout. `status` mostra o
ID, cenário, resultado e estado do ambiente. `logs` funciona também depois do
encerramento, lendo os arquivos exportados.

Cada pasta contém logs de construção e execução, resultado estruturado,
resumo do cenário e eventos. Veja a [referência do executor](cli.md) para o
significado dos arquivos e os prazos configuráveis.

Para uma leitura visual, inicie a API e o frontend conforme o
[guia do visualizador local](../tools/inspector/README.md). A tela lista as
execuções em `.tg/runs` e apresenta tarefas, saídas e eventos, com busca por
agente ou identificador. Também inclui um exemplo registrado para exploração
sem executar o Docker.

## 4. Explorar outros cenários

```sh
./tg scenario workflow-sequential
./tg scenario failure-reassignment
./tg scenario messaging-basic
```

Os três cenários dispensam LLM. O primeiro encadeia duas tarefas; o segundo
recupera a execução após um timeout; o terceiro verifica uma mensagem com
seus identificadores de correlação.

Para manter os serviços após um cenário:

```sh
./tg scenario workflow-sequential --keep
./tg logs
./tg stop
```

O encerramento atua somente na execução selecionada e preserva os arquivos
locais de resultado. Sem `--keep`, a limpeza ocorre automaticamente, inclusive
em falha ou interrupção tratada pelo executor.

## Diagnóstico rápido

| Situação | Próximo passo |
|---|---|
| Docker não responde | Inicie o Docker e execute `./tg doctor` novamente |
| Compose antigo | Atualize para >=2.24.4 |
| Falha ao construir | Leia `build.log`; confira rede e disponibilidade das dependências |
| Agente não ficou pronto | Confira `runner.log` e `services.log`; o erro identifica os agentes pendentes |
| Cenário falhou | Confira `scenario.log`, `summary.json` e eventos; após corrigir a causa, inicie uma nova execução |
| Limpeza falhou ou terminal encerrou abruptamente | Execute `./tg stop ID`, usando o ID mostrado no início |

Para publicar portas e usar um cliente no host, consulte a
[execução manual](manual-execution.md). Para escolher o próximo experimento,
consulte o [catálogo](scenarios.md).

[Índice](README.md)
