#!/usr/bin/env bash
set -euo pipefail

# Owner command (docs/owner-guide.md "Give the apps the pilot token"): save the pilot bearer token
# from the clipboard into the git-ignored pilot-token.local, which the next Android and Desktop builds
# read. It needs no Python, Java, or Android SDK, and never prints the token or its length.
# MANIJERO_CLIPBOARD_CLI and MANIJERO_PILOT_TOKEN_FILE are for tests only (fake tokens).
if [[ "${1:-}" == "--pilot-token-save" ]]; then
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  pilot_token_file="${MANIJERO_PILOT_TOKEN_FILE:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/pilot-token.local}"
  clipboard_cli="${MANIJERO_CLIPBOARD_CLI:-pbpaste}"
  if ! command -v "$clipboard_cli" >/dev/null 2>&1 || ! pilot_token="$("$clipboard_cli" 2>/dev/null)"; then
    printf 'Result: this command could not read the clipboard; it needs a Mac. Ask the developer for help.\n'
    exit 1
  fi
  # Trim surrounding whitespace and line breaks; anything inside stays and is refused below.
  pilot_token="${pilot_token#"${pilot_token%%[![:space:]]*}"}"
  pilot_token="${pilot_token%"${pilot_token##*[![:space:]]}"}"
  if [[ -z "$pilot_token" ]]; then
    printf 'Result: the clipboard is empty. Copy the pilot token first, then run this command again.\n'
    exit 1
  fi
  # Byte-wise check in this shell (the token is never a process argument): 32-512 characters of
  # A-Z a-z 0-9 - . _ ~ + / with optional trailing '=' padding.
  LC_ALL=C
  pilot_token_shape='^[A-Za-z0-9._~+/-]+=*$'
  if (( ${#pilot_token} < 32 || ${#pilot_token} > 512 )) || [[ ! "$pilot_token" =~ $pilot_token_shape ]]; then
    printf 'Result: the clipboard does not hold a pilot token. Copy the whole token again, then run this command again.\n'
    exit 1
  fi
  pilot_token_replaced=0
  [[ -e "$pilot_token_file" ]] && pilot_token_replaced=1
  # Write a private temporary file next to the target, then rename it, so a failure never leaves a
  # half-written token and never touches the previous one.
  if ! pilot_token_tmp="$(mktemp "$(dirname -- "$pilot_token_file")/.pilot-token.XXXXXX" 2>/dev/null)"; then
    printf 'Result: the pilot token could not be saved, and nothing changed. Ask the developer for help.\n'
    exit 1
  fi
  if ! { chmod 600 "$pilot_token_tmp" && printf '%s' "$pilot_token" > "$pilot_token_tmp" && mv -f "$pilot_token_tmp" "$pilot_token_file"; } 2>/dev/null; then
    rm -f "$pilot_token_tmp"
    printf 'Result: the pilot token could not be saved, and nothing changed. Ask the developer for help.\n'
    exit 1
  fi
  if (( pilot_token_replaced )); then
    printf 'Result: the pilot token is saved; it replaced the previous one. The next app build will send it.\n'
  else
    printf 'Result: the pilot token is saved. The next app build will send it.\n'
  fi
  exit 0
fi

# The backend is independent of the Android/Gradle toolchain. Handle it before
# the Android SDK and Java setup below, so it can be started on its own.
if [[ "${1:-}" == "--setup-python" ]]; then
  shift
  exec "$(dirname -- "${BASH_SOURCE[0]}")/python-env.sh" "$@"
fi

# Owner commands for the local answer tools (docs/owner-guide.md). Like --backend, they
# need no Android SDK, Java, or local.properties. MANIJERO_OLLAMA_CLI is for tests only.
if [[ "${1:-}" == "--local-rag-setup" || "${1:-}" == "--local-rag-status" ]]; then
  REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Owner commands for the local answer service over those tools (docs/owner-guide.md). The service
# runs from backend/.venv-hybrid on 127.0.0.1 only; MANIJERO_LOCAL_RAG_PORT is for tests and
# developers only.
if [[ "${1:-}" == "--local-rag-start" || "${1:-}" == "--local-rag-stop" || "${1:-}" == "--local-rag-service-status" ]]; then
  REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
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

if [[ "${1:-}" == "--backend" ]]; then
  REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Auto-detect ANDROID_HOME and local.properties if not already set
# Works from any subdirectory (including git worktrees)
if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
  # Try common macOS locations
  ANDROID_HOME="$HOME/Library/Android/sdk"
  ANDROID_SDK_ROOT="$ANDROID_HOME"
fi
ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"

# Ensure local.properties exists in current directory with SDK path
# This handles git worktrees correctly - each worktree gets its own file
if [[ ! -f "local.properties" ]]; then
  cat > local.properties <<EOF
sdk.dir=$ANDROID_HOME
EOF
  echo "Created local.properties with SDK path: $ANDROID_HOME"
fi

# Avoid conflicting AGP location environment variables
unset ANDROID_PREFS_ROOT

# Export environment variables for Gradle
export ANDROID_HOME
export ANDROID_SDK_ROOT

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Fixed date for the versioned catalog and the offline evaluators, so the checks are
# deterministic. Override with MANIJERO_AS_OF=YYYY-MM-DD when a different date matters.
AS_OF="${MANIJERO_AS_OF:-2026-10-13}"

usage() {
  cat <<'EOF'
Usage: ./scripts/init.sh [--check|--fast|--verify|--feature <id>|--backend-tests [targets]|--setup-python [dev|hybrid]|--backend|--mock|--mock-status|--mock-stop|--local-rag-setup|--local-rag-status|--local-rag-start|--local-rag-service-status|--local-rag-stop|--pilot-token-save|--android|--android-run|--desktop|--help]

  --check                   Check Java and the Gradle wrapper, then print standard commands (default)
  --fast                    Shared host tests, contract examples, backend unit tests, and the five
                            offline evaluators, run concurrently (no Android SDK or Desktop build
                            needed). Fails if any single check fails.
  --verify                  Full gate: --fast, then the Android host tests and the Android/Desktop
                            builds (--full is an alias)
  --feature <id>            Run the focused verification published in docs/specs/<id>.md
  --backend-tests [target]  Run the backend pytest suite, or only the given targets, from backend/
  --setup-python [profile]  Build or reuse the shared backend virtualenv (dev, or hybrid for
                            torch/chromadb) and link it as backend/.venv (or backend/.venv-hybrid)
  --backend                 Link the shared backend virtualenv if needed and launch the local API
  --mock                    Start the mock answer service in the background (fixed contract
                            example answers, no Python needed) and print the app addresses
  --mock-status             Say whether the mock answer service is running, and where
  --mock-stop               Stop the mock answer service
  --local-rag-setup         Guided one-time setup of the local answer tools: shows the download
                            sizes, asks, then downloads and builds what is missing (needs Ollama)
  --local-rag-status        Read-only check of the six local answer-tool parts, in plain words
  --local-rag-start         Start the real local answer service in the background (hybrid search,
                            local drafting, 127.0.0.1 only) once all six parts are ready
  --local-rag-service-status
                            Say whether the local answer service runs, can answer, and where
  --local-rag-stop          Stop the local answer service
  --pilot-token-save        Save the copied pilot token (macOS clipboard) for the next Android and
                            Desktop builds; it never prints the token
  --android                 Build the Android debug APK
  --android-run             Build, start an emulator if needed, install, and launch the app
  --desktop                 Launch the Desktop app
  --help                    Show this help

Tiers keep a small change cheap to check: --feature for one feature, --fast for the
whole no-device surface, --verify for the release-shaped gate.

Output is compact: one line per passing check and the tail of a failing log; full
logs are kept in build/verify-logs/. Set MANIJERO_VERBOSE=1 to print them inline.
EOF
}

run_android_on_emulator() {
  local sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  local adb emulator apk="$REPO_ROOT/androidApp/build/outputs/apk/debug/androidApp-debug.apk"
  local serial avd booted=0 attempt
  adb="$sdk_root/platform-tools/adb"
  emulator="$sdk_root/emulator/emulator"

  if [[ -z "$sdk_root" || ! -x "$adb" ]]; then
    printf 'Android SDK adb not found. Set ANDROID_HOME (or ANDROID_SDK_ROOT) to your SDK path.\n' >&2
    return 1
  fi

  ./gradlew :androidApp:assembleDebug

  serial="$("$adb" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }')"
  if [[ -z "$serial" ]]; then
    if [[ ! -x "$emulator" ]]; then
      printf 'Android emulator executable not found at %s. Install the Android Emulator SDK package.\n' "$emulator" >&2
      return 1
    fi
    avd="$("$emulator" -list-avds | sed -n '1p')"
    if [[ -z "$avd" ]]; then
      printf 'No Android Virtual Device (AVD) is configured. Create one in Android Studio Device Manager, then rerun --android-run.\n' >&2
      return 1
    fi
    printf 'Starting emulator AVD: %s\n' "$avd"
    "$emulator" -avd "$avd" >/dev/null 2>&1 &

  fi

  for ((attempt = 0; attempt < 240; attempt++)); do
    serial="$("$adb" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }')"
    if [[ -n "$serial" ]] && [[ "$("$adb" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      booted=1
      break
    fi
    sleep 1
  done
  if (( booted == 0 )); then
    printf 'Timed out waiting for the Android emulator to finish booting. Check the emulator window and try again.\n' >&2
    return 1
  fi

  printf 'Installing app on %s\n' "$serial"
  "$adb" -s "$serial" install -r "$apk"
  "$adb" -s "$serial" shell monkey -p com.jamarglex.manijero 1
}

if [[ ! -x "$REPO_ROOT/gradlew" ]]; then
  printf 'Gradle wrapper is missing or not executable: %s/gradlew\n' "$REPO_ROOT" >&2
  exit 1
fi

if ! command -v java >/dev/null 2>&1; then
  printf 'Java is required. Install a compatible JDK, then rerun ./scripts/init.sh.\n' >&2
  exit 1
fi

# Prints the interpreter used for the standard-library offline checks.
python_bin() {
  if [[ -n "${MANIJERO_PYTHON:-}" ]]; then
    printf '%s\n' "$MANIJERO_PYTHON"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' python
    return 0
  fi
  return 1
}

run_python() {
  local py
  if ! py="$(python_bin)"; then
    printf 'Python 3 is required for the offline checks; install it or set MANIJERO_PYTHON.\n' >&2
    return 1
  fi
  "$py" "$@"
}

# Prints the first interpreter that has pytest installed, if any.
pytest_python() {
  local candidate
  for candidate in "${MANIJERO_PYTHON:-}" "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/backend/.venv/bin/python" python3 python; do
    [[ -n "$candidate" ]] || continue
    if [[ -x "$candidate" ]] || command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import pytest' >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

backend_pytest_hint() {
  printf 'Backend unit tests need pytest. Build the shared backend virtualenv once (it is reused by every worktree):\n\n'
  printf '  ./scripts/init.sh --setup-python\n'
}

# run_backend_tests <required 0|1> [pytest targets...]
run_backend_tests() {
  local required="$1"
  shift
  local py
  # A worktree created after the shared environment was built only needs the link.
  if [[ -z "${MANIJERO_PYTHON:-}" && ! -e "$REPO_ROOT/backend/.venv" ]]; then
    "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1 || true
  fi
  if py="$(pytest_python)"; then
    if [[ "$py" != /* ]] && [[ "$py" == */* ]]; then
      py="$REPO_ROOT/$py"
    fi
    ( cd "$REPO_ROOT/backend" && "$py" -m pytest "$@" )
    return 0
  fi
  if [[ "$required" == "1" || -n "${CI:-}" ]]; then
    printf '\nBackend unit tests: pytest is not installed in any available Python interpreter.\n' >&2
    backend_pytest_hint >&2
    return 1
  fi
  printf '\n[skip] Backend unit tests: pytest is not installed.\n'
  backend_pytest_hint
  return 0
}

# Tier 1: everything that runs without an Android device, an emulator, or a Desktop run.
#
# The shared host tests, the contract validator, the backend unit tests, the
# source-catalog validator, and the five offline evaluators are read-only, offline,
# and mutually independent, so the fast tier runs them concurrently. Each job writes
# to its own log, so concurrent output never interleaves; the logs are replayed in a
# fixed order once the job has finished. Every exit code is collected before the tier
# decides, so the tier fails closed if any single check fails and never aborts a
# sibling mid-run.
#
# Output is compact by default, because agents pay for every line they read: one
# summary line per passing job, and only the tail of a failing job's log. The full
# logs stay in build/verify-logs/ for on-demand reading; MANIJERO_VERBOSE=1 replays
# them all inline, and MANIJERO_FAIL_TAIL sets how many failing-log lines to print.
VERIFY_LOG_DIR="$REPO_ROOT/build/verify-logs"
FAIL_TAIL="${MANIJERO_FAIL_TAIL:-60}"
FAST_JOB_NAMES=()
FAST_JOB_PIDS=()
FAST_JOB_LOGS=()

# fast_job <workdir> <job-name> <command...>
# Starts one fast-tier check in the background, capturing its output to
# <workdir>/<job-name>.log and registering it for run_offline_checks.
fast_job() {
  local workdir="$1" name="$2"
  shift 2
  local log="$workdir/$name.log"
  FAST_JOB_NAMES+=("$name")
  FAST_JOB_LOGS+=("$log")
  ( "$@" ) >"$log" 2>&1 &
  FAST_JOB_PIDS+=("$!")
}

run_offline_checks() {
  local workdir="$VERIFY_LOG_DIR"
  rm -rf "$workdir"
  mkdir -p "$workdir"
  FAST_JOB_NAMES=()
  FAST_JOB_PIDS=()
  FAST_JOB_LOGS=()

  fast_job "$workdir" gradle-jvm-test ./gradlew --console=plain :shared:jvmTest
  fast_job "$workdir" contract-examples run_python contracts/validate_examples.py
  fast_job "$workdir" backend-tests run_backend_tests 0 -q
  fast_job "$workdir" source-catalog run_python backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of "$AS_OF"
  fast_job "$workdir" retrieval run_python backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of "$AS_OF" --active-campaign 2026 --k 5
  fast_job "$workdir" generation run_python backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of "$AS_OF" --active-campaign 2026 --k 5
  fast_job "$workdir" abstention run_python backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of "$AS_OF" --active-campaign 2026 --k 5
  fast_job "$workdir" clarification run_python backend/scripts/evaluate_clarification.py --catalog backend/tests/fixtures/clarification/catalog.json --passages backend/tests/fixtures/clarification/passages.json --eval backend/tests/fixtures/clarification/eval_questions.jsonl --as-of "$AS_OF" --k 5
  fast_job "$workdir" land-safety run_python backend/scripts/evaluate_land_safety.py --catalog backend/tests/fixtures/land_safety/catalog.json --passages backend/tests/fixtures/land_safety/passages.json --cases backend/tests/fixtures/land_safety/cases.json --as-of "$AS_OF" --active-campaign 2026 --k 5

  printf '\nRunning %d independent offline checks concurrently...\n' "${#FAST_JOB_PIDS[@]}"

  local status=0 failed=() i code name log
  for i in "${!FAST_JOB_PIDS[@]}"; do
    code=0
    wait "${FAST_JOB_PIDS[$i]}" || code=$?
    name="${FAST_JOB_NAMES[$i]}"
    log="${FAST_JOB_LOGS[$i]}"
    if [[ -n "${MANIJERO_VERBOSE:-}" ]]; then
      printf '\n---- %s ----\n' "$name"
      cat "$log"
    elif (( code == 0 )); then
      printf '[ok]   %-18s %s\n' "$name" "$(log_summary "$log")"
    else
      printf '[FAIL] %-18s exit %d; last %d lines of %s:\n' "$name" "$code" "$FAIL_TAIL" "${log#"$REPO_ROOT"/}"
      tail -n "$FAIL_TAIL" "$log"
    fi
    if (( code != 0 )); then
      failed+=("$name")
      status=1
    fi
  done

  if (( status != 0 )); then
    printf '\nFast tier failed: %s (full logs in %s)\n' "${failed[*]}" "${workdir#"$REPO_ROOT"/}" >&2
    return 1
  fi
  printf '\nAll %d offline checks passed (full logs in %s).\n' "${#FAST_JOB_PIDS[@]}" "${workdir#"$REPO_ROOT"/}"
}

# log_summary <log>
# The last non-empty line of a log, trimmed of pytest's '=' framing, as a one-line result.
log_summary() {
  awk 'NF { last = $0 } END { print last }' "$1" | sed -e 's/^=* *//' -e 's/ *=*$//' | cut -c1-110
}

run_fast() {
  printf '\n== Fast tier: shared host tests, contract examples, backend tests, and offline evaluators ==\n'
  run_offline_checks
  printf '\nFast tier passed.\n'
}

# Prints the shell commands a feature spec publishes between the verify markers.
feature_commands() {
  local spec="$REPO_ROOT/docs/specs/$1.md"
  awk '
    /^<!-- verify:start -->$/ { in_block = 1; next }
    /^<!-- verify:end -->$/   { in_block = 0; next }
    in_block                  { print }
  ' "$spec" | sed -e '/^[[:space:]]*```/d' -e '/^[[:space:]]*$/d'
}

run_feature() {
  local id="${1:-}"
  if [[ -z "$id" ]]; then
    printf 'Usage: ./scripts/init.sh --feature <feature-id>\n' >&2
    exit 2
  fi
  local spec="$REPO_ROOT/docs/specs/$id.md"
  if [[ ! -f "$spec" ]]; then
    printf 'Unknown feature "%s": no %s\n' "$id" "$spec" >&2
    exit 2
  fi
  local commands
  commands="$(feature_commands "$id")"
  if [[ -z "$commands" ]]; then
    printf 'No focused verification published in %s (expected a <!-- verify:start --> ... <!-- verify:end --> block).\n' "$spec" >&2
    exit 2
  fi
  if [[ "$id" == "backend_answer_evaluation" ]]; then
    local validator_python candidate
    validator_python=""
    for candidate in "${MANIJERO_PYTHON:-}" "$REPO_ROOT/backend/.venv/bin/python" "$REPO_ROOT/.venv/bin/python" python3 python; do
      [[ -n "$candidate" ]] || continue
      if { [[ -x "$candidate" ]] || command -v "$candidate" >/dev/null 2>&1; } && \
        "$candidate" -c 'import pytest, jsonschema; from jsonschema import Draft202012Validator' >/dev/null 2>&1; then
        validator_python="$candidate"
        break
      fi
    done
    if [[ -z "$validator_python" ]]; then
      printf 'Focused PAC answer-evaluation checks require pytest and the Draft 2020-12 jsonschema validator in the same Python environment.\n' >&2
      printf 'Install them with: python3 -m pip install -r backend/requirements-dev.txt\n' >&2
      printf 'Then rerun with MANIJERO_PYTHON=/path/to/python ./scripts/init.sh --feature backend_answer_evaluation\n' >&2
      return 1
    fi
    export MANIJERO_PYTHON="$validator_python"
  fi
  if [[ -n "${MANIJERO_VERBOSE:-}" ]]; then
    printf '\n== Focused tier: %s (from docs/specs/%s.md) ==\n\n%s\n\n' "$id" "$id" "$commands"
  else
    printf '\n== Focused tier: %s (%d command lines from docs/specs/%s.md) ==\n' "$id" "$(printf '%s\n' "$commands" | wc -l)" "$id"
  fi
  local script status=0 tmpdir="${TMPDIR:-/tmp}"
  tmpdir="${tmpdir%/}"
  script="$(mktemp "$tmpdir/manijero-verify-XXXXXX")"
  printf '%s\n' "$commands" > "$script"
  if [[ -n "${MANIJERO_VERBOSE:-}" ]]; then
    AS_OF="$AS_OF" REPO_ROOT="$REPO_ROOT" bash -euo pipefail "$script" || status=$?
  else
    # Compact like the fast tier: the tail of the log on success, a longer tail on failure.
    local log="$VERIFY_LOG_DIR/feature-$id.log"
    mkdir -p "$VERIFY_LOG_DIR"
    AS_OF="$AS_OF" REPO_ROOT="$REPO_ROOT" bash -euo pipefail "$script" >"$log" 2>&1 || status=$?
    if (( status == 0 )); then
      tail -n 5 "$log"
      printf '\nFocused tier passed (full log in %s).\n' "${log#"$REPO_ROOT"/}"
    else
      tail -n "$FAIL_TAIL" "$log"
      printf '\nFocused tier failed with exit %d (full log in %s).\n' "$status" "${log#"$REPO_ROOT"/}" >&2
    fi
  fi
  rm -f "$script"
  return "$status"
}

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
      printf 'Port %s is in use by the real local answer service (./scripts/init.sh --local-rag-start or ./scripts/init.sh --backend).\n' "$port" >&2
      printf 'Result: the mock answer service did not start. Stop the local answer service with ./scripts/init.sh --local-rag-stop (or Ctrl+C in the window where ./scripts/init.sh --backend runs), then run ./scripts/init.sh --mock again.\n' >&2
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

mode="${1:---check}"
case "$mode" in
  --check)
    ./gradlew --version
    cat <<'EOF'

Manijero MVP — the Android and Desktop apps render the shared Kotlin Multiplatform UI and behavior in shared/src/commonMain. See PROGRESS.md and feature_list.json for the accepted feature set and current status.

Verification tiers:
  ./scripts/init.sh --feature <id>  # focused checks published in docs/specs/<id>.md
  ./scripts/init.sh --fast          # shared host tests + contract examples + backend tests + offline evaluators (concurrent)
  ./scripts/init.sh --verify        # --fast + Android host tests + Android debug APK + Desktop build

Build and run:
  ./scripts/init.sh --setup-python # build or reuse the shared backend virtualenv (once per requirements change)
  ./scripts/init.sh --backend    # start the local API (Ctrl+C to stop)
  ./scripts/init.sh --mock       # start the mock answer service: fixed example answers, no Python (--mock-status, --mock-stop)
  ./scripts/init.sh --local-rag-setup  # set up the local answer tools once (see docs/owner-guide.md)
  ./scripts/init.sh --local-rag-status # check the local answer tools in plain words
  ./scripts/init.sh --local-rag-start  # start the real local answer service in the background (--local-rag-service-status, --local-rag-stop)
  ./scripts/init.sh --android    # androidApp/build/outputs/apk/debug/androidApp-debug.apk
  ./scripts/init.sh --android-run # build and launch on an Android emulator
  ./scripts/init.sh --desktop    # launch the Desktop app

The Android and Desktop apps use the local /ask service. Start it with --local-rag-start (or keep --backend running in a separate
terminal) while trying either app, or start the mock answer service with --mock to try every answer state without Python.
EOF
    ;;
  --fast)
    run_fast
    ;;
  --verify|--full)
    run_fast
    printf '\n== Full tier: Android host tests and the Android/Desktop builds ==\n'
    # --quiet keeps task chatter out of the transcript; errors and test failures still print.
    if [[ -n "${MANIJERO_VERBOSE:-}" ]]; then
      ./gradlew --console=plain :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
    else
      ./gradlew --console=plain --quiet :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
      printf '\nFull tier passed.\n'
    fi
    ;;
  --feature)
    run_feature "${2:-}"
    ;;
  --backend-tests)
    shift
    run_backend_tests 1 "$@"
    ;;
  --backend)
    # Normally handled above, but retain a clear fallback if dispatch is changed.
    printf 'Backend startup dispatch failed unexpectedly.\n' >&2
    exit 1
    ;;
  --mock)
    mock_start
    ;;
  --mock-status)
    mock_status
    ;;
  --mock-stop)
    mock_stop
    ;;
  --android)
    ./gradlew :androidApp:assembleDebug
    ;;
  --android-run)
    run_android_on_emulator
    ;;
  --desktop)
    ./gradlew :desktopApp:run
    ;;
  --help|-h)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
