#!/bin/sh
# Infraestrutura comum; cada cenário possui sua topologia e seus casos.
set -eu
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case "${1:-}" in basic_task|agent_selection|routing|failure_reassignment) SCENARIO=$1 ;; *) echo "Cenário de benchmark inválido" >&2; exit 1 ;; esac
BENCHMARK_DIR="$ROOT_DIR/studies/scenarios/$SCENARIO/benchmarks"
RUN_ID=${BENCHMARK_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}
OUTPUT_DIR="$BENCHMARK_DIR/results/$RUN_ID"
ENV_FILE=/dev/null
if [ "$SCENARIO" = routing ]; then
  ENV_FILE=${BENCHMARK_ENV_FILE:-$ROOT_DIR/.env}
  if [ ! -f "$ENV_FILE" ]; then
    if [ -n "${BENCHMARK_ENV_FILE:-}" ]; then echo "Arquivo de ambiente não encontrado" >&2; exit 1; fi
    ENV_FILE=/dev/null
  fi
fi
mkdir -p "$OUTPUT_DIR"
compose() { docker compose --env-file "$ENV_FILE" -f "$BENCHMARK_DIR/compose.yaml" "$@"; }
cleanup() { compose down >/dev/null 2>&1 || true; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
compose up --build -d --wait
ORCHESTRATOR_ADDR="localhost:${BENCHMARK_ORCHESTRATOR_PORT:-54052}" \
BENCHMARK_OUTPUT_DIR="$OUTPUT_DIR" \
  uv run --directory "$ROOT_DIR/tools/clients/submit-task" python "$BENCHMARK_DIR/run.py"
compose cp orchestrator:/data/events.jsonl "$OUTPUT_DIR/events.jsonl"
python3 "$ROOT_DIR/tools/runtime_metrics/compute_metrics.py" \
  --events "$OUTPUT_DIR/events.jsonl" --output "$OUTPUT_DIR/task-summary.csv"
if [ "$SCENARIO" = failure_reassignment ]; then
  python3 "$ROOT_DIR/studies/scenarios/failure_reassignment/runtime_metrics/render_event_charts.py" \
    "$OUTPUT_DIR/task-summary.csv" "$OUTPUT_DIR/recovery.svg"
fi
echo "Resultados: $OUTPUT_DIR"
