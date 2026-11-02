#!/usr/bin/env bash
set -euo pipefail

# The batch loop, one command per step (logic in scripts/batch_flow.py):
#
#   .agents/skills/github-flow/scripts/batch.sh next [--note "<owner decisions>"] [--no-decisions]
#       Run the next feature of the batch in its own worktree and headless session.
#   .agents/skills/github-flow/scripts/batch.sh integrate [--partial]
#       Merge the batch's accepted features, run the checks, push, and open one PR to main.
#   .agents/skills/github-flow/scripts/batch.sh status
#       Show the current batch.
#
# Run it from the main checkout. It stops with a plain message whenever a person must decide.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${MANIJERO_PYTHON:-}" ]]; then
  py="$MANIJERO_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  py=python3
else
  printf 'The batch loop needs Python 3; install it or set MANIJERO_PYTHON.\n' >&2
  exit 1
fi

exec "$py" "$SCRIPT_DIR/batch_flow.py" "$@"
