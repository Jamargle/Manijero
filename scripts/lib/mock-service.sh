# Mock answer service: --mock, --mock-status, --mock-stop.
# ---------------------------------------------------------------------------------------------
# Local mock answer service (--mock, --mock-status, --mock-stop)
# ---------------------------------------------------------------------------------------------
# A test-only stand-in for the local answer service that serves only the committed contract
# examples (shared/src/jvmTest/.../mock). It binds to 127.0.0.1 only; the Android emulator still
# reaches it through 10.0.2.2. Pid and log files are per port under build/mock-answer-server/.
# MANIJERO_MOCK_PORT overrides the port for tests and developers only.
MOCK_MAIN_CLASS="com.jamarglex.manijero.mock.MockAnswerServerKt"
MOCK_HOST="127.0.0.1"
MOCK_STATE_DIR="$REPO_ROOT/build/mock-answer-server"
MOCK_PREPARED_DIR="$REPO_ROOT/shared/build/mock-answer-server"
MOCK_READY_SECONDS=60
MOCK_PID=""
MOCK_STALE_CLEARED=0

mock_port() {
  local port="${MANIJERO_MOCK_PORT:-8000}"
  if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
    printf 'MANIJERO_MOCK_PORT must be a port number between 1 and 65535.\n' >&2
    printf 'Result: the mock answer service was not changed.\n' >&2
    exit 2
  fi
  printf '%s\n' "$port"
}

mock_pid_file() { printf '%s/%s.pid\n' "$MOCK_STATE_DIR" "$1"; }
mock_log_file() { printf '%s/%s.log\n' "$MOCK_STATE_DIR" "$1"; }
mock_url() { printf 'http://%s:%s\n' "$MOCK_HOST" "$1"; }

# mock_pid_is_mock <pid> <port>: true only when <pid> is alive and is this mock on <port>, so a
# reused pid can never be mistaken for the mock (and never be stopped).
mock_pid_is_mock() {
  local pid="$1" port="$2" command_line
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  command_line="$(ps -ww -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command_line" == *"$MOCK_MAIN_CLASS"* && "$command_line" == *"--port $port" ]]
}

# mock_find_running <port>: sets MOCK_PID when the recorded mock is running; clears a stale record
# left by a crash, a kill, or a restart, and sets MOCK_STALE_CLEARED=1 when it did.
mock_find_running() {
  local port="$1" pid_file pid
  pid_file="$(mock_pid_file "$port")"
  MOCK_PID=""
  [[ -f "$pid_file" ]] || return 1
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if mock_pid_is_mock "$pid" "$port"; then
    MOCK_PID="$pid"
    return 0
  fi
  rm -f "$pid_file"
  MOCK_STALE_CLEARED=1
  return 1
}

mock_report_stale() {
  if (( MOCK_STALE_CLEARED == 1 )); then
    printf 'An earlier mock answer service ended without being stopped; its leftover record was cleared.\n'
  fi
}

mock_print_addresses() {
  local port="$1"
  printf '  Desktop app address:          http://127.0.0.1:%s\n' "$port"
  printf '  Android emulator app address: http://10.0.2.2:%s\n' "$port"
  if [[ "$port" == "8000" ]]; then
    printf '  These are the apps'"'"' default addresses, so nothing needs changing in the apps.\n'
  fi
}

mock_require_curl() {
  if ! command -v curl >/dev/null 2>&1; then
    printf 'The program "curl" is missing. It is needed to check the mock answer service.\n' >&2
    printf 'Result: the mock answer service did not start. Install curl (on macOS: xcode-select --install), then run ./scripts/init.sh --mock again.\n' >&2
    exit 1
  fi
}

# mock_port_owner <port>: prints "free", "backend", "mock", or "other" for 127.0.0.1:<port>.
mock_port_owner() {
  local port="$1" body code=0
  body="$(curl -s --max-time 3 "http://$MOCK_HOST:$port/health" 2>/dev/null)" || code=$?
  if (( code == 7 )); then
    printf 'free\n'
  elif [[ "$body" == *'"manijero-backend"'* ]]; then
    printf 'backend\n'
  elif [[ "$body" == *'"manijero-mock"'* ]]; then
    printf 'mock\n'
  else
    printf 'other\n'
  fi
}

mock_start() {
  local port pid_file log_file url owner java_bin classpath pid attempt
  port="$(mock_port)"
  pid_file="$(mock_pid_file "$port")"
  log_file="$(mock_log_file "$port")"
  url="$(mock_url "$port")"
  mock_require_curl

  if mock_find_running "$port"; then
    printf 'The mock answer service is already running at %s (process %s).\n' "$url" "$MOCK_PID"
    mock_print_addresses "$port"
    printf 'Result: nothing new was started; the mock answer service is already running at %s.\n' "$url"
    return 0
  fi
  mock_report_stale

  owner="$(mock_port_owner "$port")"
  case "$owner" in
    backend)
      printf 'Port %s is in use by the real local answer service (./scripts/init.sh --local-rag-start, ./scripts/init.sh --container-start, or ./scripts/init.sh --backend).\n' "$port" >&2
      printf 'Result: the mock answer service did not start. Stop the local answer service with ./scripts/init.sh --local-rag-stop or ./scripts/init.sh --container-stop (or Ctrl+C in the window where ./scripts/init.sh --backend runs), then run ./scripts/init.sh --mock again.\n' >&2
      return 1
      ;;
    mock)
      printf 'Port %s is in use by a mock answer service started from a different folder.\n' "$port" >&2
      printf 'Result: the mock answer service did not start. Run ./scripts/init.sh --mock-stop in that folder, then run ./scripts/init.sh --mock again.\n' >&2
      return 1
      ;;
    other)
      printf 'Port %s is in use by another program.\n' "$port" >&2
      printf 'Result: the mock answer service did not start. Close the other program that uses port %s, then run ./scripts/init.sh --mock again.\n' "$port" >&2
      return 1
      ;;
  esac

  mkdir -p "$MOCK_STATE_DIR"
  : > "$log_file"
  printf 'Preparing the mock answer service (the first run can take a few minutes)...\n'
  if ! ./gradlew --console=plain --quiet :shared:prepareMockAnswerServer >>"$log_file" 2>&1 \
    || [[ ! -s "$MOCK_PREPARED_DIR/java.txt" || ! -s "$MOCK_PREPARED_DIR/classpath.txt" ]]; then
    printf 'The mock answer service could not be prepared. Details are in %s\n' "${log_file#"$REPO_ROOT"/}" >&2
    printf 'Result: the mock answer service did not start. Run ./scripts/init.sh --mock again; if it fails again, share that log file.\n' >&2
    return 1
  fi
  java_bin="$(tr -d '\n' < "$MOCK_PREPARED_DIR/java.txt")"
  classpath="$(tr -d '\n' < "$MOCK_PREPARED_DIR/classpath.txt")"

  printf 'Starting the mock answer service...\n'
  CLASSPATH="$classpath" nohup "$java_bin" "$MOCK_MAIN_CLASS" \
    --examples "$REPO_ROOT/contracts/examples" --host "$MOCK_HOST" --port "$port" \
    </dev/null >>"$log_file" 2>&1 &
  pid=$!
  printf '%s\n' "$pid" > "$pid_file"

  for ((attempt = 0; attempt < MOCK_READY_SECONDS * 2; attempt++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pid_file"
      local reason
      reason="$(grep -h 'Mock answer service cannot start:' "$log_file" | tail -n 1 || true)"
      printf '%s\n' "${reason:-The mock answer service stopped while starting.}" >&2
      printf 'Details are in %s\n' "${log_file#"$REPO_ROOT"/}" >&2
      if [[ "$reason" == *"example file"* ]]; then
        printf 'Result: the mock answer service did not start. Put back the original example file named above (download the project again if unsure), then run ./scripts/init.sh --mock again.\n' >&2
      else
        printf 'Result: the mock answer service did not start. Run ./scripts/init.sh --mock again; if it fails again, share that log file.\n' >&2
      fi
      return 1
    fi
    if curl -fsS --max-time 2 "$url/health" 2>/dev/null | grep -q '"service":"manijero-mock"'; then
      printf '\nThe mock answer service is running. The apps will show fixed example answers, not real ones.\n'
      mock_print_addresses "$port"
      printf 'Next steps:\n'
      printf '  ./scripts/init.sh --desktop      open the Desktop app\n'
      printf '  ./scripts/init.sh --android-run  open the app on the Android emulator\n'
      printf '  ./scripts/init.sh --mock-stop    stop the mock answer service when you are done\n'
      printf 'Log file: %s\n' "${log_file#"$REPO_ROOT"/}"
      printf 'Result: the mock answer service started at %s.\n' "$url"
      return 0
    fi
    sleep 0.5
  done

  kill "$pid" 2>/dev/null || true
  rm -f "$pid_file"
  printf 'The mock answer service did not answer within %s seconds. Details are in %s\n' "$MOCK_READY_SECONDS" "${log_file#"$REPO_ROOT"/}" >&2
  printf 'Result: the mock answer service did not start. Run ./scripts/init.sh --mock again.\n' >&2
  return 1
}

mock_status() {
  local port url
  port="$(mock_port)"
  url="$(mock_url "$port")"
  if mock_find_running "$port"; then
    printf 'The mock answer service is running at %s (process %s).\n' "$url" "$MOCK_PID"
    mock_print_addresses "$port"
    local log_file
    log_file="$(mock_log_file "$port")"
    printf 'Log file: %s\n' "${log_file#"$REPO_ROOT"/}"
    printf 'Result: the mock answer service is running at %s.\n' "$url"
    return 0
  fi
  mock_report_stale
  printf 'Result: the mock answer service is not running. Start it with ./scripts/init.sh --mock.\n'
  return 1
}

mock_stop() {
  local port attempt
  port="$(mock_port)"
  if ! mock_find_running "$port"; then
    mock_report_stale
    printf 'Result: the mock answer service was not running, so there was nothing to stop.\n'
    return 0
  fi
  kill -TERM "$MOCK_PID" 2>/dev/null || true
  for ((attempt = 0; attempt < 20; attempt++)); do
    kill -0 "$MOCK_PID" 2>/dev/null || break
    sleep 0.5
  done
  # Still the verified mock process after 10 seconds: end it for sure.
  if mock_pid_is_mock "$MOCK_PID" "$port"; then
    kill -KILL "$MOCK_PID" 2>/dev/null || true
    sleep 0.5
  fi
  rm -f "$(mock_pid_file "$port")"
  printf 'Result: the mock answer service has stopped.\n'
  return 0
}
