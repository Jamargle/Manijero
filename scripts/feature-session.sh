#!/usr/bin/env bash
set -euo pipefail

# Starts a fresh agent session that runs feature-flow for exactly one feature.
# One session per feature keeps each feature's context small: nothing from an
# earlier feature's reads, reports, or commits is carried into the next one.
#
# Usage: ./scripts/feature-session.sh [--agent claude|codex|opencode] [--headless] [--note <text>]
#                                     [feature-id] [agent options...]
#   With no feature id, uses the selector's next feature. Extra options go to the agent CLI.
#   The agent defaults to MANIJERO_AGENT, or claude.
#   --headless  run without a terminal UI (github-flow worktree sessions): edits are accepted inside
#               the checkout, push and gh are refused, and the output is saved under
#               build/agent-sessions/. Claude runs also print one usage line and append it to
#               build/agent-sessions/usage.tsv.
#   --note      a short handoff added to the prompt, for example an owner decision. Prefer a fresh
#               session with a note over resuming a long one: a resume replays its whole history.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

usage() { sed -n '8,9p' "${BASH_SOURCE[0]}" | sed 's/^# //' >&2; exit 2; }

agent="${MANIJERO_AGENT:-claude}"
headless=0
note=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) [[ $# -ge 2 ]] || usage; agent="$2"; shift 2 ;;
    --headless) headless=1; shift ;;
    --note) [[ $# -ge 2 ]] || usage; note="$2"; shift 2 ;;
    *) break ;;
  esac
done
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

# Preflight: give the session a working Java so direct ./gradlew calls work too (init.sh resolves
# Java on its own). A missing Java is not fatal here; the first check that needs it says so.
# shellcheck source=scripts/java-env.sh
source "$REPO_ROOT/scripts/java-env.sh"
manijero_resolve_java || printf 'Note: %s\n' "$MANIJERO_JAVA_MISSING" >&2

prompt="Use feature-flow for $id only, until accepted."
if [[ -n "$note" ]]; then
  prompt="$prompt Handoff from the orchestrator: $note"
fi

if (( headless == 0 )); then
  printf 'Starting a new %s session for %s\n' "$agent" "$id"
  case "$agent" in
    claude) exec claude "$@" "$prompt" ;;
    codex) exec codex "$@" "$prompt" ;;
    opencode) exec opencode "$@" --prompt "$prompt" ;;
  esac
fi

log_dir="${MANIJERO_AGENT_LOG_DIR:-$REPO_ROOT/build/agent-sessions}"  # the override is for tests only
mkdir -p "$log_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
log="$log_dir/$id-$stamp.log"
printf 'Starting a headless %s session for %s (output: %s)\n' "$agent" "$id" "$log"

case "$agent" in
  claude)
    # The owner-approved scope for headless feature sessions: edits inside this checkout, the
    # project scripts, Python, Gradle, and local git commits. Push, gh, and amend stay with the
    # orchestrator. The prompt goes on stdin so a list flag can never swallow it.
    allowed="Read,Edit,Write,Glob,Grep,Agent,Task,SendMessage,Skill,TodoWrite"
    allowed+=",Bash(./scripts/*),Bash(CI=true ./scripts/*),Bash(./gradlew:*),Bash(python3:*)"
    allowed+=",Bash(backend/.venv/bin/*),Bash(java:*),Bash(git add:*),Bash(git commit:*)"
    allowed+=",Bash(git status:*),Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(git mv:*)"
    allowed+=",Bash(git rev-parse:*),Bash(ls:*),Bash(grep:*),Bash(wc:*),Bash(chmod:*),Bash(mkdir:*)"
    status=0
    printf '%s\n' "$prompt" | claude -p --output-format json --permission-mode acceptEdits \
      --allowedTools "$allowed" \
      --disallowedTools "Bash(git push:*),Bash(gh:*),Bash(git commit --amend:*),Bash(docker:*)" \
      "$@" > "$log" 2>&1 || status=$?
    python3 - "$log" "$log_dir/usage.tsv" "$id" "$stamp" <<'PY' || true
import json, sys
log, tsv, feature, stamp = sys.argv[1:5]
try:
    data = json.loads(open(log, encoding="utf-8").read().strip().splitlines()[-1])
except (ValueError, IndexError, OSError):
    print("Usage: not reported (see the output file).")
    sys.exit(0)
print(data.get("result", ""))
models = data.get("modelUsage") or {}
tokens = {k: sum(int(v.get(f, 0) or 0) for v in models.values())
          for f, k in (("inputTokens", "input"), ("outputTokens", "output"),
                       ("cacheReadInputTokens", "cache_read"), ("cacheCreationInputTokens", "cache_write"))}
if not models:
    u = data.get("usage") or {}
    tokens = {"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
              "cache_read": u.get("cache_read_input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0)}
cost = data.get("total_cost_usd", 0) or 0
turns = data.get("num_turns", 0)
minutes = round((data.get("duration_ms", 0) or 0) / 60000, 1)
print("Usage: {} turns, {} min, input {input}, output {output}, cache read {cache_read}, cache write {cache_write}, "
      "about ${:.2f} at API prices; models: {}".format(turns, minutes, cost, ", ".join(sorted(models)) or "-", **tokens))
new = False
try:
    open(tsv, encoding="utf-8").close()
except OSError:
    new = True
with open(tsv, "a", encoding="utf-8") as out:
    if new:
        out.write("stamp\tfeature\tturns\tminutes\tinput\toutput\tcache_read\tcache_write\tcost_usd\n")
    out.write("{}\t{}\t{}\t{}\t{input}\t{output}\t{cache_read}\t{cache_write}\t{:.4f}\n".format(
        stamp, feature, turns, minutes, cost, **tokens))
PY
    exit "$status"
    ;;
  codex)
    # --full-auto: workspace-write sandbox, so the session can edit and run checks in this checkout.
    exec codex exec --full-auto --json "$@" "$prompt" > "$log" 2>&1
    ;;
  opencode)
    # Permissions come from .opencode/agents/*.md and the user's OpenCode configuration.
    exec opencode run "$@" "$prompt" > "$log" 2>&1
    ;;
esac
