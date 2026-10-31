#!/usr/bin/env bash
set -euo pipefail

# Starts a fresh agent session that runs feature-flow for exactly one feature.
# One session per feature keeps each feature's context small: nothing from an
# earlier feature's reads, reports, or commits is carried into the next one.
#
# Usage: ./scripts/feature-session.sh [--agent claude|codex|opencode] [feature-id] [agent options...]
#   With no feature id, uses the selector's next feature. Extra options go to the agent CLI.
#   The agent defaults to MANIJERO_AGENT, or claude.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

agent="${MANIJERO_AGENT:-claude}"
if [[ "${1:-}" == "--agent" ]]; then
  agent="${2:-}"
  shift 2 || { printf 'Usage: --agent claude|codex|opencode\n' >&2; exit 2; }
fi
case "$agent" in
  claude|codex|opencode) ;;
  *) printf 'Unknown agent "%s": use claude, codex, or opencode\n' "$agent" >&2; exit 2 ;;
esac

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

if ! command -v "$agent" >/dev/null 2>&1; then
  printf 'The %s CLI is not on PATH.\n' "$agent" >&2
  exit 1
fi

prompt="Use feature-flow for $id only, until accepted."
printf 'Starting a new %s session for %s\n' "$agent" "$id"
case "$agent" in
  claude) exec claude "$@" "$prompt" ;;
  codex) exec codex "$@" "$prompt" ;;
  opencode) exec opencode "$@" --prompt "$prompt" ;;
esac
