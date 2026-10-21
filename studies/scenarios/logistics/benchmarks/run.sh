#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)
RUN_ID=${LOGISTICS_RUN_ID:-logistics-$(date -u +%Y%m%dT%H%M%SZ)}
OUTPUT_DIR="$ROOT_DIR/studies/scenarios/logistics/benchmarks/results/$RUN_ID"
COMPOSE_FILE="$ROOT_DIR/studies/scenarios/logistics/docker/compose.yaml"
ENV_FILE=${BENCHMARK_ENV_FILE:-$ROOT_DIR/.env}

if [ ! -f "$ENV_FILE" ]; then
  echo "Arquivo de ambiente ausente: $ENV_FILE" >&2
  echo "Crie .env com OPENAI_API_KEY para executar LLM-only e híbrido." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
cleanup() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up \
  --build -d --wait registry orchestrator bdi-agent llm-agent
ORCHESTRATOR_ADDR="localhost:${BENCHMARK_ORCHESTRATOR_PORT:-54052}" \
LOGISTICS_OUTPUT_DIR="$OUTPUT_DIR" \
  uv run --directory "$ROOT_DIR/tools/clients/submit-task" \
  python "$ROOT_DIR/studies/scenarios/logistics/benchmarks/run.py"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
  cp orchestrator:/data/events.jsonl "$OUTPUT_DIR/events.jsonl"

echo "Resultados: $OUTPUT_DIR"
