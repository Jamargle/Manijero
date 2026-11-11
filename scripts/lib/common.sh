# shellcheck shell=bash
# Shared paths and defaults for ./scripts/init.sh and the modules it sources.
# Sourced, never run on its own. It does not change the working directory: --check and the
# local.properties write still act on the directory the owner ran the command from.
SCRIPTS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MANIJERO_ROOT="$(cd -- "$SCRIPTS_DIR/.." && pwd)"
REPO_ROOT="$MANIJERO_ROOT"

# Fixed date for the versioned catalog and the offline evaluators, so the checks are
# deterministic. Override with MANIJERO_AS_OF=YYYY-MM-DD when a different date matters.
AS_OF="${MANIJERO_AS_OF:-2026-10-13}"
