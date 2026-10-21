#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)
RUN_ID=${BENCHMARK_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}
OUTPUT_DIR="$ROOT_DIR/studies/scenarios/runtime_comparison/benchmarks/results/$RUN_ID"
COMPOSE_FILE="$ROOT_DIR/studies/scenarios/runtime_comparison/benchmarks/compose.yaml"
ENV_FILE=${BENCHMARK_ENV_FILE:-$ROOT_DIR/.env}

if [ ! -f "$ENV_FILE" ]; then
  echo "Arquivo de ambiente ausente: $ENV_FILE" >&2
  echo "Crie .env com OPENAI_API_KEY para executar os cenários C e E." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
cleanup() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --build -d --wait
ORCHESTRATOR_ADDR="localhost:${BENCHMARK_ORCHESTRATOR_PORT:-54052}" \
BENCHMARK_OUTPUT_DIR="$OUTPUT_DIR" \
  uv run --directory "$ROOT_DIR/tools/clients/submit-task" \
  python "$ROOT_DIR/studies/scenarios/runtime_comparison/benchmarks/run.py"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
  cp orchestrator:/data/events.jsonl "$OUTPUT_DIR/events.jsonl"
PYTHONPATH="$ROOT_DIR/tools/runtime_metrics" python3 \
  "$ROOT_DIR/tools/runtime_metrics/compute_metrics.py" \
  --events "$OUTPUT_DIR/events.jsonl" \
  --output "$OUTPUT_DIR/task-summary.csv"
python3 "$ROOT_DIR/studies/scenarios/runtime_comparison/runtime_metrics/render_event_charts.py" \
  "$OUTPUT_DIR/task-summary.csv" "$OUTPUT_DIR/recovery.svg"

echo "Resultados: $OUTPUT_DIR"
