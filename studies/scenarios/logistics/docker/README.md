# Missão logística LLM + BDI

Este guia mantém o cenário Docker histórico. Para a interface declarativa
atual e avaliação separada da execução, use o
[estudo em studies/scenarios/logistics](../README.md).

O exemplo recebe linguagem natural, usa a LLM somente para extrair as
restrições e entrega a missão estruturada ao agente BDI. O BDI encontra uma
sequência determinística e um simulador do domínio confirma precondições,
energia, prazo, locais obrigatórios/proibidos e estado final.

Crie `.env` na raiz com `OPENAI_API_KEY` antes de iniciar. O modelo pode ser
configurado por `LLM_MODEL` e deve estar disponível à conta. Este exemplo usa
a topologia de benchmarks, com Orchestrator na porta 54052 por padrão.

## Execução recomendada

Com Docker e Compose >=2.24.4 e a chave configurada, na raiz:

```sh
./ariadne doctor logistics-mission
./ariadne scenario logistics-mission
```

O executor usa uma instância isolada da topologia de benchmarks, sem publicar
portas, e salva resultado e avaliação em `.ariadne/runs/ID/`. Há chamadas reais à
LLM. Veja a [referência](../../../../docs/cli.md).

## Execução manual (Python e uv no host)

```sh
docker compose --env-file .env -f studies/scenarios/logistics/docker/compose.yaml up \
  --build -d --wait registry orchestrator mission-planner mission-assistant

uv run --project sdk/python \
  python studies/scenarios/logistics/docker/scenario.py

docker compose --env-file .env -f studies/scenarios/logistics/docker/compose.yaml down
```

O caso demonstrado exige entrega em H, passagem por D, proíbe C, estabelece
reserva mínima de bateria e deadline. O comando falha se o plano produzido não
passar no oráculo determinístico.

O simulador compartilha regras e o planejador de referência com o BDI; consulte
o [guia de avaliação](../../../../docs/evaluation.md) para metodologia e limitações.

[Catálogo de cenários](../../../../docs/scenarios.md)
