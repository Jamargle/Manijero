#!/usr/bin/env bash
set -euo pipefail

# Auto-detect ANDROID_HOME and local.properties if not already set
# Works from any subdirectory (including git worktrees)
if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
  # Try common macOS locations
  ANDROID_HOME="$HOME/Library/Android/sdk"
  ANDROID_SDK_ROOT="$ANDROID_HOME"
fi

# Ensure local.properties exists in current directory with SDK path
# This handles git worktrees correctly - each worktree gets its own file
if [[ ! -f "local.properties" ]]; then
  cat > local.properties <<EOF
sdk.dir=$ANDROID_HOME
EOF
  echo "Created local.properties with SDK path: $ANDROID_HOME"
fi

# Export environment variables for Gradle
export ANDROID_HOME
export ANDROID_SDK_ROOT

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Fixed date for the versioned catalog and the offline evaluators, so the checks are
# deterministic. Override with MANIJERO_AS_OF=YYYY-MM-DD when a different date matters.
AS_OF="${MANIJERO_AS_OF:-2026-10-13}"

usage() {
  cat <<'EOF'
Usage: ./init.sh [--check|--fast|--verify|--feature <id>|--backend-tests [targets]|--android|--desktop|--help]

  --check                   Check Java and the Gradle wrapper, then print standard commands (default)
  --fast                    Shared host tests, contract examples, backend unit tests, and the five
                            offline evaluators (no Android SDK or Desktop build needed)
  --verify                  Full gate: --fast, then the Android host tests and the Android/Desktop
                            builds (--full is an alias)
  --feature <id>            Run the focused verification published in docs/specs/<id>.md
  --backend-tests [target]  Run the backend pytest suite, or only the given targets, from backend/
  --android                 Build the Android debug APK
  --desktop                 Launch the Desktop app
  --help                    Show this help

Tiers keep a small change cheap to check: --feature for one feature, --fast for the
whole no-device surface, --verify for the release-shaped gate.
EOF
}

if [[ ! -x "$REPO_ROOT/gradlew" ]]; then
  printf 'Gradle wrapper is missing or not executable: %s/gradlew\n' "$REPO_ROOT" >&2
  exit 1
fi

if ! command -v java >/dev/null 2>&1; then
  printf 'Java is required. Install a compatible JDK, then rerun ./init.sh.\n' >&2
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
  for candidate in "${MANIJERO_PYTHON:-}" python3 python; do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import pytest' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

backend_pytest_hint() {
  printf 'Backend unit tests need pytest. Install it in a local virtualenv and point the harness at it:\n\n'
  printf '  python3 -m venv "${TMPDIR:-/tmp}/manijero-venv"\n'
  printf '  "${TMPDIR:-/tmp}/manijero-venv/bin/pip" install -r backend/requirements.txt pytest\n'
  printf '  MANIJERO_PYTHON="${TMPDIR:-/tmp}/manijero-venv/bin/python" ./init.sh --verify\n'
}

# run_backend_tests <required 0|1> [pytest targets...]
run_backend_tests() {
  local required="$1"
  shift
  local py
  if py="$(pytest_python)"; then
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
run_fast() {
  printf '\n== Fast tier: shared host tests, contract examples, and backend checks ==\n'
  ./gradlew :shared:jvmTest
  run_python contracts/validate_examples.py
  run_backend_tests 0
  run_python backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of "$AS_OF"
  run_python backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of "$AS_OF" --k 5
  run_python backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of "$AS_OF" --k 5
  run_python backend/scripts/evaluate_abstention.py --catalog backend/tests/fixtures/abstention/catalog.json --passages backend/tests/fixtures/abstention/passages.json --eval backend/tests/fixtures/abstention/eval_questions.jsonl --as-of "$AS_OF" --k 5
  run_python backend/scripts/evaluate_clarification.py --catalog backend/tests/fixtures/clarification/catalog.json --passages backend/tests/fixtures/clarification/passages.json --eval backend/tests/fixtures/clarification/eval_questions.jsonl --as-of "$AS_OF" --k 5
  run_python backend/scripts/evaluate_land_safety.py --catalog backend/tests/fixtures/land_safety/catalog.json --passages backend/tests/fixtures/land_safety/passages.json --cases backend/tests/fixtures/land_safety/cases.json --as-of "$AS_OF" --k 5
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
    printf 'Usage: ./init.sh --feature <feature-id>\n' >&2
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
  printf '\n== Focused tier: %s (from docs/specs/%s.md) ==\n\n%s\n\n' "$id" "$id" "$commands"
  local script status=0 tmpdir="${TMPDIR:-/tmp}"
  tmpdir="${tmpdir%/}"
  script="$(mktemp "$tmpdir/manijero-verify-XXXXXX")"
  printf '%s\n' "$commands" > "$script"
  AS_OF="$AS_OF" REPO_ROOT="$REPO_ROOT" bash -euo pipefail "$script" || status=$?
  rm -f "$script"
  return "$status"
}

mode="${1:---check}"
case "$mode" in
  --check)
    ./gradlew --version
    cat <<'EOF'

Manijero MVP — the Android and Desktop apps render the shared Kotlin Multiplatform UI and behavior in shared/src/commonMain. See PROGRESS.md and feature_list.json for the accepted feature set and current status.

Verification tiers:
  ./init.sh --feature <id>  # focused checks published in docs/specs/<id>.md
  ./init.sh --fast          # shared host tests + contract examples + backend tests + offline evaluators
  ./init.sh --verify        # --fast + Android host tests + Android debug APK + Desktop build

Build and run:
  ./init.sh --android    # androidApp/build/outputs/apk/debug/androidApp-debug.apk
  ./init.sh --desktop    # launch the Desktop app

Known limitation: the backend has no /ask route yet, so the shipped app answers a question with the plain-Spanish failure notice and a Reintentar button, not a grounded answer.
EOF
    ;;
  --fast)
    run_fast
    ;;
  --verify|--full)
    run_fast
    printf '\n== Full tier: Android host tests and the Android/Desktop builds ==\n'
    ./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
    ;;
  --feature)
    run_feature "${2:-}"
    ;;
  --backend-tests)
    shift
    run_backend_tests 1 "$@"
    ;;
  --android)
    ./gradlew :androidApp:assembleDebug
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
