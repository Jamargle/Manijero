#!/usr/bin/env bash
# Check the local project layout and print the supported startup commands.

set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f settings.gradle.kts || ! -f gradlew ]]; then
  echo "Error: Manijero Gradle project files were not found in $PROJECT_ROOT" >&2
  exit 1
fi

echo "Manijero project: $PROJECT_ROOT"
echo "Kotlin Multiplatform client scaffold is present. Backend and Docker services are not configured yet."
echo
echo "Start Desktop:                            ./gradlew :desktopApp:run"
echo "Build Android:                            ./gradlew :androidApp:assembleDebug"
echo "Start backend services (ChromaDB, etc.):  docker compose up -d"
echo "Run shared JVM tests:                     ./gradlew :shared:jvmTest"

# Exit successfully — this is intentional for the pre-bootstrap phase
echo "✅ Directory confirmed. Bootstrap pending — run 'docker compose up -d' to start services."
exit 0