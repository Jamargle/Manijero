# Verification tiers and their helpers: --fast, --verify/--full, --feature, --backend-tests.
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
  fast_job "$workdir" harness-tests run_backend_tests 0 -q "$REPO_ROOT/.agents/skills"
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

# Tier 2 (inside --verify): compare the agreed retrieval and abstention metrics with the
# committed, owner-reviewed baseline. Read-only, offline, and deterministic; it runs once
# after --fast and before the builds, and its non-zero exit fails the tier.
run_quality_gate() {
  local candidate py=""
  # A worktree created after the shared environment was built only needs the link.
  if [[ -z "${MANIJERO_PYTHON:-}" && ! -e "$REPO_ROOT/backend/.venv" ]]; then
    "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1 || true
  fi
  for candidate in "${MANIJERO_PYTHON:-}" "$REPO_ROOT/backend/.venv/bin/python" "$REPO_ROOT/.venv/bin/python" python3 python; do
    [[ -n "$candidate" ]] || continue
    if { [[ -x "$candidate" ]] || command -v "$candidate" >/dev/null 2>&1; } && \
      PYTHONPATH="$REPO_ROOT/backend" "$candidate" -c 'import fastapi, httpx; import app.main' >/dev/null 2>&1; then
      py="$candidate"
      break
    fi
  done
  if [[ -z "$py" ]]; then
    printf 'The quality gate needs the backend environment (FastAPI and httpx).\n' >&2
    backend_pytest_hint >&2
    return 1
  fi
  printf '\n== Quality gate: reviewed baseline for the retrieval and abstention metrics ==\n'
  "$py" "$REPO_ROOT/backend/scripts/check_quality_gate.py" check
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

# Tier 3 (--verify): the fast tier, the quality gate, then the Android and Desktop builds.
run_full_tier() {
  run_fast
  run_quality_gate
  printf '\n== Full tier: Android host tests and the Android/Desktop builds ==\n'
  # --quiet keeps task chatter out of the transcript; errors and test failures still print.
  if [[ -n "${MANIJERO_VERBOSE:-}" ]]; then
    ./gradlew --console=plain :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
  else
    ./gradlew --console=plain --quiet :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
    printf '\nFull tier passed.\n'
  fi
}
