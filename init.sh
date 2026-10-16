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

usage() {
  cat <<'EOF'
Usage: ./init.sh [--check|--verify|--android|--desktop|--help]

  --check    Check Java and the Gradle wrapper, then print standard commands (default)
  --verify   Run shared host tests and build Android and Desktop targets
  --android  Build the Android debug APK
  --desktop  Launch the Desktop app
  --help     Show this help
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

mode="${1:---check}"
case "$mode" in
  --check)
    ./gradlew --version
    cat <<'EOF'

Manijero MVP — the Android and Desktop apps render the shared Kotlin Multiplatform UI and behavior in shared/src/commonMain. See PROGRESS.md and feature_list.json for the accepted feature set and current status.

Standard verification:
  ./init.sh --verify     # shared tests + Android debug APK + Desktop build

Build and run:
  ./init.sh --android    # androidApp/build/outputs/apk/debug/androidApp-debug.apk
  ./init.sh --desktop    # launch the Desktop app

Known limitation: the backend has no /ask route yet, so the shipped app answers a question with the plain-Spanish failure notice and a Reintentar button, not a grounded answer.
EOF
    ;;
  --verify)
    ./gradlew :shared:jvmTest :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build
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
