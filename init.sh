#!/usr/bin/env bash
set -euo pipefail

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

Product features are not implemented yet; this checkout contains the KMP starter scaffold.
Standard verification:
  ./init.sh --verify

Run targets:
  ./init.sh --android
  ./init.sh --desktop
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
