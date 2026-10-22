# Seleção de agentes

Compara FIRST_AVAILABLE, ROUND_ROBIN e LEAST_LOADED entre três trabalhadores
aptos para a mesma tarefa. As cargas reportadas são controladas (0,7; 0,1; 0,4),
portanto não representam medições de uso de CPU.

```sh
./ariadne run studies/scenarios/agent_selection/scenario.py
POLICY=LEAST_LOADED ./ariadne run studies/scenarios/agent_selection/scenario.py
sh studies/scenarios/agent_selection/benchmarks/run.sh
```

A entrada [scenario.py](scenario.py) declara os agentes e tarefas locais.
A demonstração local usa nove tarefas; o benchmark usa doze por política.
O [benchmark B](benchmarks/README.md) compara as três políticas contra uma
topologia Docker própria, aguardando a telemetria inicial. Nenhum usa LLM.

[Todos os estudos](../../README.md)
