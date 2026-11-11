#!/usr/bin/env bash
set -euo pipefail

# Owner-facing entry point: one named command per operation. The implementation is grouped by
# what it touches, under scripts/commands/ for the early-exit owner commands (they need no
# Python, Java, Android SDK, or local.properties) and scripts/lib/ for the toolchain, the
# verification tiers, the apps, the mock service, and the help text. Every module is sourced
# from here, so guides, tests, and the owner keep calling this one path.
SCRIPTS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/lib/common.sh
source "$SCRIPTS_DIR/lib/common.sh"

# Commands that exit before the toolchain checks. Keep them ahead of toolchain.sh.
# shellcheck source=scripts/commands/pilot-token.sh
source "$SCRIPTS_DIR/commands/pilot-token.sh"
# shellcheck source=scripts/commands/python.sh
source "$SCRIPTS_DIR/commands/python.sh"

# The one Java resolution for every path that runs ./gradlew or java (scripts/java-env.sh).
# shellcheck source=scripts/java-env.sh
source "$SCRIPTS_DIR/java-env.sh"

# shellcheck source=scripts/commands/local-service.sh
source "$SCRIPTS_DIR/commands/local-service.sh"
# shellcheck source=scripts/commands/qa.sh
source "$SCRIPTS_DIR/commands/qa.sh"
# shellcheck source=scripts/commands/knowledge.sh
source "$SCRIPTS_DIR/commands/knowledge.sh"

# Function definitions for the remaining modes, then the toolchain block that reads the SDK,
# writes local.properties when missing, and resolves Java.
# shellcheck source=scripts/lib/usage.sh
source "$SCRIPTS_DIR/lib/usage.sh"
# shellcheck source=scripts/lib/tiers.sh
source "$SCRIPTS_DIR/lib/tiers.sh"
# shellcheck source=scripts/lib/android.sh
source "$SCRIPTS_DIR/lib/android.sh"
# shellcheck source=scripts/lib/mock-service.sh
source "$SCRIPTS_DIR/lib/mock-service.sh"
# shellcheck source=scripts/lib/toolchain.sh
source "$SCRIPTS_DIR/lib/toolchain.sh"

mode="${1:---check}"
case "$mode" in
  --check)
    ./gradlew --version
    print_standard_commands
    ;;
  --fast)
    run_fast
    ;;
  --verify|--full)
    run_full_tier
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
    build_android
    ;;
  --android-run)
    run_android_on_emulator
    ;;
  --desktop)
    run_desktop
    ;;
  --android-qa)
    build_android_qa "$@"
    ;;
  --desktop-qa)
    run_desktop_qa "$@"
    ;;
  --help|-h)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
