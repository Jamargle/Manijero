# Local answer service: --backend, --local-rag-*, --container-*, --monitoring-*, --local-smoke, --demo-rehearsal.
# Owner commands for the local answer tools (docs/owner-guide/local-answer-service.md). Like --backend, they
# need no Android SDK, Java, or local.properties. MANIJERO_OLLAMA_CLI is for tests only.
if [[ "${1:-}" == "--local-rag-setup" || "${1:-}" == "--local-rag-status" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ "$1" == "--local-rag-setup" ]]; then
    if ! command -v "${MANIJERO_OLLAMA_CLI:-ollama}" >/dev/null 2>&1; then
      printf 'Ollama is not installed on this computer. Install it from https://ollama.com/download, open it once, then run ./scripts/init.sh --local-rag-setup again.\n'
      printf 'Result: setup stopped before changing anything.\n'
      exit 1
    fi
    if [[ ! -x "$LOCAL_RAG_PYTHON" ]]; then
      printf 'Preparing the setup tools (first time only)...\n'
      if ! "$REPO_ROOT/scripts/python-env.sh" dev; then
        printf 'The setup tools could not be prepared. Follow the step printed above, then run ./scripts/init.sh --local-rag-setup again.\n'
        printf 'Result: setup stopped.\n'
        exit 1
      fi
    fi
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/local_rag.py" setup
  fi
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/local_rag.py" status
fi

# Owner commands for the local answer service over those tools (docs/owner-guide/local-answer-service.md). The service
# runs from backend/.venv-hybrid on 127.0.0.1 only; MANIJERO_LOCAL_RAG_PORT is for tests and
# developers only.
if [[ "${1:-}" == "--local-rag-start" || "${1:-}" == "--local-rag-stop" || "${1:-}" == "--local-rag-service-status" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PORT="${MANIJERO_LOCAL_RAG_PORT:-8000}"
  if [[ ! "$LOCAL_RAG_PORT" =~ ^[0-9]{1,5}$ ]] || (( 10#$LOCAL_RAG_PORT < 1 || 10#$LOCAL_RAG_PORT > 65535 )); then
    printf 'MANIJERO_LOCAL_RAG_PORT must be a port number between 1 and 65535.\n' >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    if [[ "$1" == "--local-rag-stop" ]]; then
      printf 'Result: the local answer service was not running, so there was nothing to stop.\n'
      exit 0
    fi
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  case "$1" in
    --local-rag-start) LOCAL_RAG_COMMAND=start ;;
    --local-rag-stop) LOCAL_RAG_COMMAND=stop ;;
    *) LOCAL_RAG_COMMAND=service-status ;;
  esac
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/local_rag.py" "$LOCAL_RAG_COMMAND"
fi

# Owner command: measure answer latency and throughput at pilot concurrency against the running
# local answer service (docs/owner-guide/local-checks.md "Measure answer speed under pilot load"). Like the
# other --local-rag-* commands it runs before the local.properties write and needs no Android SDK
# or Java. It reads no port from the environment; backend/scripts/measure_local_load.py checks the
# verified run record and its three checks, then runs the plan.
if [[ "${1:-}" == "--local-rag-load-test" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/measure_local_load.py"
fi

# Owner commands for the answer service as a container in Docker Desktop (docs/owner-guide/container.md).
# The image packages the local knowledge release and search model; Ollama stays on this Mac.
# MANIJERO_DOCKER_CLI is for tests only; MANIJERO_LOCAL_RAG_PORT for tests and developers only.
if [[ "${1:-}" == "--container-build" || "${1:-}" == "--container-start" || "${1:-}" == "--container-status" || "${1:-}" == "--container-stop" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PORT="${MANIJERO_LOCAL_RAG_PORT:-8000}"
  if [[ ! "$LOCAL_RAG_PORT" =~ ^[0-9]{1,5}$ ]] || (( 10#$LOCAL_RAG_PORT < 1 || 10#$LOCAL_RAG_PORT > 65535 )); then
    printf 'MANIJERO_LOCAL_RAG_PORT must be a port number between 1 and 65535.\n' >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    if [[ "$1" == "--container-stop" ]]; then
      printf 'Result: the answer service in the container was not running, so there was nothing to stop.\n'
      exit 0
    fi
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/local_rag.py" "${1#--}"
fi

# Owner commands for the health dashboard (Prometheus and Grafana in Docker Desktop, docs/owner-guide/monitoring.md).
# It reads /metrics of the local (and, once set up, QA) answer service. MANIJERO_DOCKER_CLI is for tests
# only; MANIJERO_MONITORING_PORT and MANIJERO_LOCAL_RAG_PORT for tests and developers only.
if [[ "${1:-}" == "--monitoring-start" || "${1:-}" == "--monitoring-status" || "${1:-}" == "--monitoring-stop" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  for MONITORING_PORT_VALUE in "${MANIJERO_LOCAL_RAG_PORT:-8000}" "${MANIJERO_MONITORING_PORT:-3000}"; do
    if [[ ! "$MONITORING_PORT_VALUE" =~ ^[0-9]{1,5}$ ]] || (( 10#$MONITORING_PORT_VALUE < 1 || 10#$MONITORING_PORT_VALUE > 65535 )); then
      printf 'MANIJERO_LOCAL_RAG_PORT and MANIJERO_MONITORING_PORT must be port numbers between 1 and 65535.\n' >&2
      exit 2
    fi
  done
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    if [[ "$1" == "--monitoring-stop" ]]; then
      printf 'Result: the health dashboard was not running, so there was nothing to stop.\n'
      exit 0
    fi
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/monitoring.py" "${1#--monitoring-}"
fi

# Owner command: smoke-test the Desktop and Android emulator apps against the running local answer
# service (docs/owner-guide/local-checks.md). Like --local-rag-*, it runs before the local.properties write; AGP
# reads ANDROID_HOME instead. backend/app/local_smoke.py checks the service, Java, and the emulator.
if [[ "${1:-}" == "--local-smoke" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the smoke test did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
    ANDROID_HOME="$HOME/Library/Android/sdk"
  fi
  ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
  unset ANDROID_PREFS_ROOT
  export ANDROID_HOME ANDROID_SDK_ROOT
  # Resolve Java here but let local_smoke.py report a missing one in its own order (after the
  # service check); it accepts only the JAVA_HOME exported here.
  manijero_resolve_java || true
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/local_rag.py" smoke
fi

# Owner command: rehearse the demo (docs/owner-guide/local-checks.md, docs/demo-script.md). It checks the
# running local answer service and the reviewed-update gate, changes nothing, and runs before the
# local.properties write like the other answer-service commands.
if [[ "${1:-}" == "--demo-rehearsal" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the demo rehearsal did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/demo_rehearsal.py"
fi

if [[ "${1:-}" == "--backend" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  BACKEND_DIR="$REPO_ROOT/backend"
  VENV="$BACKEND_DIR/.venv"
  if [[ ! -x "$VENV/bin/python" ]]; then
    MANIJERO_BASE_PYTHON="${MANIJERO_BASE_PYTHON:-${MANIJERO_PYTHON:-}}" "$REPO_ROOT/scripts/python-env.sh" dev
  fi
  cd "$BACKEND_DIR"
  export MANIJERO_ACTIVE_CAMPAIGN="${MANIJERO_ACTIVE_CAMPAIGN:-2026}"
  # Android emulators reach the host through 10.0.2.2, not the host's loopback
  # interface directly. Keep the bind configurable for local development.
  BACKEND_HOST="${MANIJERO_BACKEND_HOST:-0.0.0.0}"
  exec "$VENV/bin/python" -m uvicorn app.main:app --reload --host "$BACKEND_HOST"
fi
