#!/bin/sh
# Backend Docker privado; a CLI pública valida os argumentos antes da chamada.
set -eu
: "${ARIADNE_ROOT:?invoke through ariadne}"
export ARIADNE_ROOT
RUNS=${ARIADNE_RUNS_DIR:-"$ARIADNE_ROOT/.ariadne/runs"}
case "$RUNS" in /*) ;; *) RUNS="$PWD/$RUNS" ;; esac
STATE=$(dirname -- "$RUNS")

die() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
select_scenario() {
    scenario=$1
    llm=no
    case "$scenario" in
        demo) base=tools/deploy/docker-compose.yml; services='registry orchestrator execution-simulator' ;;
        workflow-sequential) base=studies/scenarios/sequential_workflow/docker/compose.yaml; services='registry orchestrator text-echo' ;;
        failure-reassignment) base=studies/scenarios/failure_reassignment/docker/compose.yaml; services='registry orchestrator slow-agent healthy-agent' ;;
        messaging-basic) base=studies/scenarios/messaging/docker/compose.yaml; services=messaging ;;
        heterogeneous-route) base=studies/scenarios/routing/docker/compose.yaml; services='registry orchestrator route-planner planner-explainer'; llm=yes ;;
        logistics-mission) base=studies/scenarios/logistics/docker/compose.yaml; services='registry orchestrator mission-planner mission-assistant'; llm=yes ;;
        *) die "Cenário desconhecido: $scenario. Consulte ./ariadne scenario." ;;
    esac
    env_file=/dev/null
    if [ "$llm" = yes ]; then
        if [ -n "${ARIADNE_ENV_FILE:-}" ]; then
            case "$ARIADNE_ENV_FILE" in /*) env_file=$ARIADNE_ENV_FILE ;; *) env_file="$ARIADNE_ROOT/$ARIADNE_ENV_FILE" ;; esac
            [ -f "$env_file" ] || die "ARIADNE_ENV_FILE não encontrado: $env_file"
        elif [ "$scenario" = heterogeneous-route ] && [ -f "$ARIADNE_ROOT/studies/scenarios/routing/docker/.env" ]; then
            env_file="$ARIADNE_ROOT/studies/scenarios/routing/docker/.env"
        elif [ -f "$ARIADNE_ROOT/.env" ]; then
            env_file="$ARIADNE_ROOT/.env"
        fi
    fi
}

check_tools() {
    command -v docker >/dev/null 2>&1 || die 'Docker não encontrado. Instale e inicie o Docker.'
    version=$(docker compose version --short 2>/dev/null) || die 'Docker Compose v2 não disponível.'
    printf '%s\n' "$version" | awk -F. '{gsub(/^v/, "", $1); exit !(($1+0>2)||($1+0==2 && ($2+0>24 || ($2+0==24 && $3+0>=4))))}' \
        || die "Docker Compose $version: é necessário >=2.24.4."
    docker info >/dev/null 2>&1 || die 'Docker indisponível. Inicie o daemon e confira seu acesso com docker info.'
}

timeout_value() {
    case "$2" in ''|*[!0-9]*) die "$1 deve ser um inteiro entre 1 e 3600." ;; esac
    [ "$2" -ge 1 ] && [ "$2" -le 3600 ] || die "$1 deve estar entre 1 e 3600."
}

# A descrição de controle não contém ambiente/credenciais nem caminhos de build.
# Ela permite logs/down mesmo se a configuração LLM tiver sido removida.
configuration() {
    printf 'services:\n' > "$run_dir/override.yaml"
    printf 'services:\n' > "$run_dir/control.yaml"
    for service in $services; do
        printf '  %s:\n    ports: !reset []\n    restart: on-failure\n' "$service" >> "$run_dir/override.yaml"
        printf '  %s:\n    image: scratch\n' "$service" >> "$run_dir/control.yaml"
        case "$service" in
            orchestrator|messaging) printf '    volumes:\n      - events_data:/data\n' >> "$run_dir/control.yaml" ;;
        esac
    done
    printf '  runner:\n    image: scratch\nvolumes:\n  events_data: {}\n' >> "$run_dir/control.yaml"
}

compose() {
    docker compose --env-file "$env_file" -p "$project" \
        -f "$ARIADNE_ROOT/$base" -f "$run_dir/override.yaml" \
        -f "$ARIADNE_ROOT/tools/launcher/runner.compose.yaml" "$@"
}

control() {
    docker compose --env-file /dev/null -p "$project" -f "$run_dir/control.yaml" "$@"
}

doctor() (
    select_scenario "$1"
    check_tools
    run_dir=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-doctor.XXXXXX")
    trap 'rm -rf -- "$run_dir"' EXIT
    project=ariadne-doctor
    ARIADNE_RUN_DIR=$run_dir
    export ARIADNE_RUN_DIR
    configuration
    compose config --quiet || die 'Configuração inválida. Para LLM, confira OPENAI_API_KEY e ARIADNE_ENV_FILE.'
    printf 'OK: Docker e Compose %s; cenário %s configurado.\n' "$version" "$scenario"
    printf 'Cliente em contêiner; nenhuma porta publicada no host.\n'
    [ "$llm" = no ] || printf 'A configuração LLM existe; acesso ao modelo só é verificado na execução real.\n'
)

collect() {
    export_complete=yes
    if control logs --no-color > "$run_dir/services.log.tmp" 2>> "$run_dir/diagnostics.log"; then
        if [ -s "$run_dir/services.log.tmp" ]; then mv "$run_dir/services.log.tmp" "$run_dir/services.log"; fi
    fi
    rm -f "$run_dir/services.log.tmp"
    # Nunca substituir um arquivo já exportado por uma tentativa vazia após down.
    for service in orchestrator messaging; do
        grep -q "^  $service:" "$run_dir/control.yaml" || continue
        case "$service" in orchestrator) filename=events.jsonl ;; messaging) filename=message-events.jsonl ;; esac
        if control cp "$service:/data/$filename" "$run_dir/$filename.tmp" >> "$run_dir/diagnostics.log" 2>&1; then
            mv "$run_dir/$filename.tmp" "$run_dir/$filename"
        else
            rm -f "$run_dir/$filename.tmp"
            export_complete=no
        fi
    done
    return 0
}

shutdown() {
    volume_flag=
    if [ "${export_complete:-no}" = yes ]; then
        volume_flag=--volumes
    else
        printf 'Exportação incompleta: eventual volume %s_events_data será preservado.\n' "$project" >&2
    fi
    if control down $volume_flag --remove-orphans --timeout 5 >> "$run_dir/cleanup.log" 2>&1; then
        printf 'stopped\n' > "$run_dir/environment"
    else
        printf 'cleanup-failed\n' > "$run_dir/environment"
        printf 'Não foi possível encerrar tudo. Repita: ./ariadne stop %s\n' "$run_id" >&2
        return 1
    fi
}

finish() {
    code=$?
    trap - EXIT INT TERM
    if [ -n "${child:-}" ]; then
        kill "$child" 2>/dev/null || true
        wait "$child" 2>/dev/null || true
    fi
    if [ -f "$run_dir/stop-requested" ] || [ "$code" -eq 130 ] || [ "$code" -eq 143 ]; then
        outcome=CANCELLED
        code=130
    elif [ "$code" -eq 0 ]; then
        outcome=COMPLETED
    else
        outcome=FAILED
    fi
    printf '%s\n' "$outcome" > "$run_dir/status"
    if [ "$outcome" = CANCELLED ] || [ ! -f "$run_dir/environment" ] || [ "$(cat "$run_dir/environment")" != stopped ]; then
        collect
        if [ "$keep" = no ] || [ "$outcome" = CANCELLED ]; then
            shutdown || code=1
        else
            printf 'Ambiente mantido. Para encerrar: ./ariadne stop %s\n' "$run_id"
        fi
    fi
    printf 'Estado: %s\nResultados: %s\n' "$outcome" "$run_dir"
    if [ "$outcome" = FAILED ]; then
        printf 'Confira ./ariadne logs %s e os arquivos build.log/diagnostics.log.\n' "$run_id" >&2
    fi
    exit "$code"
}

run_scenario() {
    select_scenario "$1"
    keep=$2
    check_tools
    ARIADNE_READY_TIMEOUT=${ARIADNE_READY_TIMEOUT:-90}
    ARIADNE_SCENARIO_TIMEOUT=${ARIADNE_SCENARIO_TIMEOUT:-180}
    timeout_value ARIADNE_READY_TIMEOUT "$ARIADNE_READY_TIMEOUT"
    timeout_value ARIADNE_SCENARIO_TIMEOUT "$ARIADNE_SCENARIO_TIMEOUT"
    export ARIADNE_READY_TIMEOUT ARIADNE_SCENARIO_TIMEOUT
    mkdir -p "$RUNS"
    run_dir=$(mktemp -d "$RUNS/ariadne-$(date -u +%Y%m%d-%H%M%S)-XXXXXX")
    run_id=${run_dir##*/}
    project=$(printf '%s' "$run_id" | tr '[:upper:]' '[:lower:]')
    ARIADNE_RUN_DIR=$run_dir
    export ARIADNE_RUN_DIR
    configuration
    printf '%s\n' "$scenario" > "$run_dir/scenario"
    printf 'RUNNING\n' > "$run_dir/status"
    printf 'starting\n' > "$run_dir/environment"
    printf '%s\n' "$run_id" > "$STATE/latest.$run_id"
    mv "$STATE/latest.$run_id" "$STATE/latest"
    child=
    trap finish EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    printf 'Execução: %s\nCenário: %s\n' "$run_id" "$scenario"
    compose config --quiet 2> "$run_dir/diagnostics.log" || die 'Configuração inválida. Confira a configuração LLM quando aplicável.'
    [ "$llm" = no ] || printf 'Este cenário faz chamadas reais à LLM configurada.\n'
    printf 'Preparando imagens (o primeiro build pode demorar). Log: %s/build.log\n' "$run_dir"
    compose build $services runner > "$run_dir/build.log" 2>&1 &
    child=$!
    wait "$child" || die 'Build falhou; veja build.log.'
    child=
    [ ! -f "$run_dir/stop-requested" ] || exit 130
    printf 'Iniciando serviços em rede isolada…\n'
    compose up -d $services > "$run_dir/startup.log" 2>&1 &
    child=$!
    wait "$child" || die 'Inicialização falhou; veja startup.log.'
    child=
    [ ! -f "$run_dir/stop-requested" ] || exit 130
    printf 'running\n' > "$run_dir/environment"
    printf 'Aguardando serviços e registro dos agentes; executando cenário…\n'
    compose run --rm --no-deps -T --name "$project-runner" runner "$scenario" > "$run_dir/runner.log" 2>&1 &
    child=$!
    wait "$child" || { cat "$run_dir/runner.log"; die 'Cenário falhou ou excedeu o prazo.'; }
    child=
    cat "$run_dir/runner.log"
}

command=$1
shift
case "$command" in
    doctor) doctor "${1:-demo}" ;;
    demo|scenario)
        if [ "$command" = demo ]; then name=demo; else name=$1; shift; fi
        keep=no
        if [ "${1:-}" = --keep ]; then keep=yes; fi
        run_scenario "$name" "$keep"
        ;;
    stop|logs-live)
        run_dir=$1
        run_id=${run_dir##*/}
        project=$(printf '%s' "$run_id" | tr '[:upper:]' '[:lower:]')
        if [ "$command" = logs-live ]; then control logs --no-color --tail=100; exit; fi
        check_tools
        if [ "$(cat "$run_dir/status")" = RUNNING ]; then
            : > "$run_dir/stop-requested"
            printf 'CANCELLED\n' > "$run_dir/status"
        fi
        collect
        shutdown
        printf 'Ambiente encerrado: %s\nResultados preservados: %s\n' "$run_id" "$run_dir"
        ;;
    *) die "Unknown Docker backend operation: $command" ;;
esac
