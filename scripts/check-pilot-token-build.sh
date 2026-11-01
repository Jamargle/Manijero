#!/usr/bin/env bash
# Build-injection check for the pilot bearer token (docs/specs/client_pilot_credentials.md).
#
# Uses only fake tokens in a mktemp -d folder, passed through MANIJERO_PILOT_TOKEN_FILE, so the
# owner's real pilot-token.local is never read by this script. It asserts that:
#   - a valid fake file reaches the Android BuildConfig (debug and release) and the Desktop resource;
#   - an invalid fake fails the Android and Desktop builds without its content in the output;
#   - no file yields PILOT_TOKEN = null and no Desktop resource.
# It ends by regenerating without the override, so build/ holds no fake. It prints no token.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WORK="$(mktemp -d)"
FAKE_TOKEN="fakeBuildCheckTokenOnly-0123456789abcdefABCDEF+/="
INVALID_CONTENT="fake invalid content NOT-A-TOKEN-7f3a"
TASKS=(:androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig :desktopApp:processResources)
DEBUG_CONFIG="androidApp/build/generated/source/buildConfig/debug/com/jamarglex/manijero/BuildConfig.java"
RELEASE_CONFIG="androidApp/build/generated/source/buildConfig/release/com/jamarglex/manijero/BuildConfig.java"
DESKTOP_RESOURCES=(desktopApp/build/generated/pilotToken/manijero/pilot-token.txt desktopApp/build/resources/main/manijero/pilot-token.txt)
MESSAGE="pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again."

regenerated=0
cleanup() {
  local status=$?
  if (( ! regenerated )); then
    # Never leave a fake in build/, even after a failed assertion.
    env -u MANIJERO_PILOT_TOKEN_FILE ./gradlew --quiet "${TASKS[@]}" >"$WORK/final.log" 2>&1 || true
  fi
  rm -rf "$WORK"
  exit "$status"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$1"
  if [[ -n "${2:-}" && -f "$2" ]]; then
    tail -n 20 "$2"
  fi
  exit 1
}

gradle_with() {
  # $1: token file, $2: log file, rest: tasks.
  local token_file="$1" log="$2"
  shift 2
  MANIJERO_PILOT_TOKEN_FILE="$token_file" ./gradlew --quiet "$@" >"$log" 2>&1
}

# 1. A valid fake token reaches every host.
printf '%s\n' "$FAKE_TOKEN" > "$WORK/valid.local"
gradle_with "$WORK/valid.local" "$WORK/valid.log" "${TASKS[@]}" || fail "the build with a valid fake token failed" "$WORK/valid.log"
for config in "$DEBUG_CONFIG" "$RELEASE_CONFIG"; do
  grep -qF "String PILOT_TOKEN = \"$FAKE_TOKEN\";" "$config" || fail "$config does not hold the fake token"
done
for resource in "${DESKTOP_RESOURCES[@]}"; do
  [[ -f "$resource" && "$(cat "$resource")" == "$FAKE_TOKEN" ]] || fail "$resource does not hold the fake token"
done
grep -qF "$FAKE_TOKEN" "$WORK/valid.log" && fail "the build output shows the token"
printf 'PASS: a valid fake token reaches Android debug and release BuildConfig and the Desktop resource\n'

# 2. An invalid fake fails each host's build with the plain message and never its content.
printf '%s\n' "$INVALID_CONTENT" > "$WORK/invalid.local"
for task in :androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig :desktopApp:processResources; do
  log="$WORK/invalid${task//:/-}.log"
  if gradle_with "$WORK/invalid.local" "$log" "$task"; then
    fail "$task succeeded with an invalid token file"
  fi
  grep -qF "$MESSAGE" "$log" || fail "$task did not print the plain message" "$log"
  grep -qF "NOT-A-TOKEN" "$log" && fail "$task output shows the token file's content"
done
printf 'PASS: an invalid fake fails the Android and Desktop builds without showing its content\n'

# 3. No token file: PILOT_TOKEN is null and there is no Desktop resource.
gradle_with "$WORK/missing.local" "$WORK/missing.log" "${TASKS[@]}" || fail "the build without a token file failed" "$WORK/missing.log"
for config in "$DEBUG_CONFIG" "$RELEASE_CONFIG"; do
  grep -qF "String PILOT_TOKEN = null;" "$config" || fail "$config does not set PILOT_TOKEN = null"
done
for resource in "${DESKTOP_RESOURCES[@]}"; do
  [[ ! -e "$resource" ]] || fail "$resource exists without a token file"
done
printf 'PASS: without a token file PILOT_TOKEN is null and there is no Desktop resource\n'

# 4. Regenerate without the override, so build/ holds no fake.
env -u MANIJERO_PILOT_TOKEN_FILE ./gradlew --quiet "${TASKS[@]}" >"$WORK/final.log" 2>&1 \
  || fail "the final build without the override failed" "$WORK/final.log"
regenerated=1
for generated in "$DEBUG_CONFIG" "$RELEASE_CONFIG" "${DESKTOP_RESOURCES[@]}"; do
  if [[ -f "$generated" ]] && grep -qF "$FAKE_TOKEN" "$generated"; then
    fail "$generated still holds the fake token"
  fi
done
printf 'Result: the pilot token build check passed; build outputs hold no fake token.\n'
