#!/usr/bin/env bash
# init.sh — Ayudante Agrícola
# Standard startup/verification path (provisional — product bootstrap pending)
#
# This script confirms the project directory and reports that product bootstrap
# is pending. It will be replaced with a full bootstrap script after the minimal
# repo harness is established and the technical bootstrap phase begins.

set -euo pipefail

echo "========================================="
echo "Ayudante Agrícola — Startup Script"
echo "========================================="
echo ""

# Confirm we are in the right directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"
echo ""

# Report product bootstrap status
echo "⚠️  Product bootstrap is pending."
echo "   The minimal repo harness has been created."
echo "   Full setup (Docker, backend, database) will be configured in the"
echo "   technical bootstrap phase."
echo ""

# List expected future commands (when known)
echo "Expected future commands (informational):"
echo "  ./gradlew :androidApp:assembleDebug    # Build Android APK"
echo "  ./gradlew :desktopApp:run             # Run Desktop app"
echo "  docker compose up -d                    # Start backend services (ChromaDB, etc.)"
echo "  ./gradlew :shared:jvmTest              # Run unit tests"
echo ""

# Exit successfully — this is intentional for the pre-bootstrap phase
echo "✅ Directory confirmed. Bootstrap pending — run 'docker compose up -d' to start services."
exit 0