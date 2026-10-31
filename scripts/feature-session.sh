#!/usr/bin/env bash
set -euo pipefail

# Starts a fresh Claude Code session that runs feature-flow for exactly one feature.
# One session per feature keeps each feature's context small: nothing from an
# earlier feature's reads, reports, or commits is carried into the next one.
#
# Usage: ./scripts/feature-session.sh [feature-id] [claude options...]
#   With no feature id, uses the selector's next feature. Extra options go to `claude`.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

id=""
if [[ $# -gt 0 && "$1" != -* ]]; then
  id="$1"
  shift
fi

if [[ -z "$id" ]]; then
  selection="$(./scripts/select-feature.sh --next)"
  id="$(printf '%s\n' "$selection" | sed -n 's/^NEXT_FEATURE=//p')"
  role="$(printf '%s\n' "$selection" | sed -n 's/^NEXT_ROLE=//p')"
  if [[ -z "$id" || "$role" == "none" ]]; then
    printf 'No feature is ready to run:\n%s\n' "$selection" >&2
    exit 1
  fi
fi

if [[ ! -f "docs/specs/$id.md" ]] && ! grep -q "\"id\": \"$id\"" feature_list.json; then
  printf 'Unknown feature "%s": not in feature_list.json\n' "$id" >&2
  exit 2
fi

if ! command -v claude >/dev/null 2>&1; then
  printf 'The claude CLI is not on PATH.\n' >&2
  exit 1
fi

printf 'Starting a new Claude Code session for %s\n' "$id"
exec claude "$@" "Use feature-flow for $id only, until accepted."
