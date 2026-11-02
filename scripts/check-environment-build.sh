#!/usr/bin/env bash
# Build-output check for the local and QA environment builds (docs/specs/client_environment_builds.md).
#
# Uses only fake address and key files in a mktemp -d folder, passed through MANIJERO_QA_ADDRESS_FILE,
# MANIJERO_QA_HOME, and MANIJERO_PILOT_TOKEN_FILE, so it never reads pilot-token.local, qa-address.local,
# or anything under ~/manijero. It asserts that:
#   - the local default (with a malformed address file and a QA key present) keeps the local id, label,
#     address, and no token, and the Desktop resource says local;
#   - a QA build has the .qa id, the label Manijero QA, the file address, and the QA key in the debug
#     BuildConfig and the Desktop run folder only; release and every jar carry no token;
#   - no address file gives the placeholder and one notice;
#   - a bad environment, address, or key fails with the plain message and without echoing content.
# It ends by regenerating in local mode, so build/ holds no fake and no QA output. It prints no key.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WORK="$(mktemp -d)"
FAKE_KEY="fakeQaAccessKeyOnly-0123456789abcdefABCDEF+/="
FAKE_ADDRESS="https://qa.example.org:8443/api"
INVALID_CONTENT="fake invalid content NOT-A-VALUE-7f3a"
PLACEHOLDER="https://qa.manijero.invalid"
MISSING_TOKEN="$WORK/missing-token.local"
QA_HOME="$WORK/qa-home"
mkdir -p "$QA_HOME/credentials"
printf '%s\n' "$FAKE_KEY" > "$QA_HOME/credentials/qa-test-device.token"
EMPTY_QA_HOME="$WORK/empty-qa-home"
mkdir -p "$EMPTY_QA_HOME"

ANDROID_TASKS=(:androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig :androidApp:processDebugMainManifest)
DESKTOP_TASKS=(:desktopApp:generateEnvironmentResource :desktopApp:generatePilotTokenResource :desktopApp:jar)
DEBUG_CONFIG="androidApp/build/generated/source/buildConfig/debug/com/jamarglex/manijero/BuildConfig.java"
RELEASE_CONFIG="androidApp/build/generated/source/buildConfig/release/com/jamarglex/manijero/BuildConfig.java"
ENVIRONMENT_RESOURCE="desktopApp/build/generated/environment/manijero/environment.properties"
TOKEN_RESOURCE="desktopApp/build/generated/pilotToken/manijero/pilot-token.txt"
DESKTOP_JAR="desktopApp/build/libs/desktopApp.jar"

regenerated=0
cleanup() {
  local status=$?
  if (( ! regenerated )); then
    # Never leave a fake or a QA output in build/, even after a failed assertion.
    local_build "$WORK/final.log" "${ANDROID_TASKS[@]}" "${DESKTOP_TASKS[@]}" >/dev/null 2>&1 || true
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

# Local mode: the token override points at a missing path, so pilot-token.local is never read; the
# QA address file is malformed and a QA key exists, to prove local ignores both.
printf '%s\n' "$INVALID_CONTENT" > "$WORK/invalid-address.local"
local_build() {
  # $1: log file, rest: Gradle arguments.
  local log="$1"
  shift
  MANIJERO_PILOT_TOKEN_FILE="$MISSING_TOKEN" MANIJERO_QA_HOME="$QA_HOME" \
    MANIJERO_QA_ADDRESS_FILE="$WORK/invalid-address.local" ./gradlew --quiet "$@" >"$log" 2>&1
}

# QA mode: $1 address file, $2 QA home, $3 log, rest: Gradle arguments (the QA property is added).
qa_build() {
  local address_file="$1" qa_home="$2" log="$3"
  shift 3
  env -u MANIJERO_PILOT_TOKEN_FILE MANIJERO_QA_ADDRESS_FILE="$address_file" MANIJERO_QA_HOME="$qa_home" \
    ./gradlew --quiet -PmanijeroEnvironment=qa "$@" >"$log" 2>&1
}

# Any Gradle run with the given -P setting; the QA files point at the temp folder.
setting_build() {
  local setting="$1" log="$2"
  shift 2
  env -u MANIJERO_PILOT_TOKEN_FILE MANIJERO_QA_ADDRESS_FILE="$WORK/none.local" MANIJERO_QA_HOME="$EMPTY_QA_HOME" \
    ./gradlew --quiet "$setting" "$@" >"$log" 2>&1
}

merged_manifest() {
  find androidApp/build/intermediates -path '*merged_manifest*' -path '*debug*' -name AndroidManifest.xml | head -n 1
}

has_line() { grep -qF "$1" "$2"; }

assert_no_secret_outputs() {
  # No generated or packaged output may hold the QA key, except the Desktop run folder and debug config.
  [[ -f "$DESKTOP_JAR" ]] || fail "$DESKTOP_JAR was not built"
  unzip -l "$DESKTOP_JAR" | grep -qF "pilot-token" && fail "the Desktop jar contains a pilot-token entry"
  unzip -p "$DESKTOP_JAR" | grep -aqF "$FAKE_KEY" && fail "the Desktop jar contains the QA key"
  has_line "String PILOT_TOKEN = null;" "$RELEASE_CONFIG" || fail "release BuildConfig does not set PILOT_TOKEN = null"
  grep -qF "$FAKE_KEY" "$RELEASE_CONFIG" && fail "release BuildConfig holds the QA key"
  [[ ! -e "desktopApp/build/resources/main/manijero/pilot-token.txt" ]] || fail "main resources hold a token resource"
  return 0
}

# 1. Local default: unchanged id, label, address, no token, Desktop resource says local.
local_build "$WORK/local.log" "${ANDROID_TASKS[@]}" "${DESKTOP_TASKS[@]}" || fail "the local default build failed" "$WORK/local.log"
for config in "$DEBUG_CONFIG" "$RELEASE_CONFIG"; do
  has_line 'String APPLICATION_ID = "com.jamarglex.manijero";' "$config" || fail "local application id changed in $config"
  has_line 'String MANIJERO_ENVIRONMENT = "local";' "$config" || fail "local MANIJERO_ENVIRONMENT is not local in $config"
  has_line 'String ASK_BASE_URL = "http://10.0.2.2:8000";' "$config" || fail "local ASK_BASE_URL changed in $config"
  has_line "String PILOT_TOKEN = null;" "$config" || fail "local PILOT_TOKEN is not null in $config"
done
manifest="$(merged_manifest)"
[[ -n "$manifest" ]] || fail "no merged debug manifest was found"
grep -qF 'android:label="@string/app_name"' "$manifest" || fail "the local label is not @string/app_name"
[[ "$(cat "$ENVIRONMENT_RESOURCE")" == "environment=local" ]] || fail "the local Desktop resource is not environment=local"
[[ ! -e "$TOKEN_RESOURCE" ]] || fail "the local build produced a Desktop token resource"
grep -rqF "$FAKE_KEY" "$DEBUG_CONFIG" "$RELEASE_CONFIG" && fail "a local BuildConfig holds the QA key"
assert_no_secret_outputs
local_build "$WORK/local-explicit.log" -PmanijeroEnvironment=local :androidApp:generateDebugBuildConfig :desktopApp:generateEnvironmentResource \
  || fail "-PmanijeroEnvironment=local failed" "$WORK/local-explicit.log"
has_line 'String APPLICATION_ID = "com.jamarglex.manijero";' "$DEBUG_CONFIG" || fail "explicit local changed the application id"
printf 'PASS: local default keeps the id, label, address, and no token, and ignores a bad address file and the QA key\n'

# 2. QA with a valid address and key: separate app, file address, key in test builds only.
printf '  %s/  \n' "$FAKE_ADDRESS" > "$WORK/address.local"
qa_build "$WORK/address.local" "$QA_HOME" "$WORK/qa.log" -PmanijeroAskBaseUrl=http://127.0.0.1:1 \
  "${ANDROID_TASKS[@]}" "${DESKTOP_TASKS[@]}" || fail "the QA build failed" "$WORK/qa.log"
has_line 'String APPLICATION_ID = "com.jamarglex.manijero.qa";' "$DEBUG_CONFIG" || fail "QA debug application id is not .qa"
has_line 'String APPLICATION_ID = "com.jamarglex.manijero.qa";' "$RELEASE_CONFIG" || fail "QA release application id is not .qa"
for config in "$DEBUG_CONFIG" "$RELEASE_CONFIG"; do
  has_line 'String MANIJERO_ENVIRONMENT = "qa";' "$config" || fail "QA MANIJERO_ENVIRONMENT is not qa in $config"
  has_line "String ASK_BASE_URL = \"$FAKE_ADDRESS\";" "$config" || fail "QA ASK_BASE_URL is not the file address in $config"
done
has_line "String PILOT_TOKEN = \"$FAKE_KEY\";" "$DEBUG_CONFIG" || fail "QA debug BuildConfig does not hold the QA key"
manifest="$(merged_manifest)"
grep -qF 'android:label="Manijero QA"' "$manifest" || fail "the QA label is not Manijero QA"
printf 'environment=qa\naskBaseUrl=%s\n' "$FAKE_ADDRESS" | cmp -s - "$ENVIRONMENT_RESOURCE" || fail "the QA Desktop resource is wrong"
[[ -f "$TOKEN_RESOURCE" && "$(cat "$TOKEN_RESOURCE")" == "$FAKE_KEY" ]] || fail "the QA Desktop run folder does not hold the QA key"
unzip -p "$DESKTOP_JAR" manijero/environment.properties | cmp -s - "$ENVIRONMENT_RESOURCE" || fail "the Desktop jar lacks the QA environment resource"
grep -qF "$FAKE_KEY" "$WORK/qa.log" && fail "the QA build output shows the key"
assert_no_secret_outputs
printf 'PASS: QA builds a .qa app named Manijero QA at the file address; the key reaches only the debug config and the Desktop run folder\n'

# 3. Switching back to local reuses no QA output.
local_build "$WORK/back.log" "${ANDROID_TASKS[@]}" "${DESKTOP_TASKS[@]}" || fail "the build back to local failed" "$WORK/back.log"
has_line 'String APPLICATION_ID = "com.jamarglex.manijero";' "$DEBUG_CONFIG" || fail "switching back to local kept the QA id"
has_line "String PILOT_TOKEN = null;" "$DEBUG_CONFIG" || fail "switching back to local kept the QA key"
[[ "$(cat "$ENVIRONMENT_RESOURCE")" == "environment=local" ]] || fail "switching back to local kept the QA resource"
[[ ! -e "$TOKEN_RESOURCE" ]] || fail "switching back to local kept the QA key resource"
unzip -p "$DESKTOP_JAR" manijero/environment.properties | grep -qF "qa" && fail "the local jar still holds the QA resource"
printf 'PASS: switching QA to local reuses no QA output\n'

# 4. QA without an address file: the placeholder and one notice. No key: PILOT_TOKEN is null.
qa_build "$WORK/none.local" "$EMPTY_QA_HOME" "$WORK/placeholder.log" --no-configuration-cache \
  :androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig || fail "the QA build without an address file failed" "$WORK/placeholder.log"
has_line "String ASK_BASE_URL = \"$PLACEHOLDER\";" "$DEBUG_CONFIG" || fail "the placeholder address is missing"
has_line "String PILOT_TOKEN = null;" "$DEBUG_CONFIG" || fail "QA without a key does not give PILOT_TOKEN = null"
notice="The QA address is a placeholder ($PLACEHOLDER) until the QA server is chosen; this app cannot reach QA yet."
[[ "$(grep -cF "$notice" "$WORK/placeholder.log")" == "1" ]] || fail "the placeholder notice did not print exactly once" "$WORK/placeholder.log"
qa_build "$WORK/none.local" "$EMPTY_QA_HOME" "$WORK/placeholder-desktop.log" :desktopApp:generateEnvironmentResource \
  || fail "the QA Desktop build without an address file failed" "$WORK/placeholder-desktop.log"
printf 'environment=qa\naskBaseUrl=%s\n' "$PLACEHOLDER" | cmp -s - "$ENVIRONMENT_RESOURCE" || fail "the Desktop placeholder resource is wrong"
printf 'PASS: QA without an address file uses the placeholder with one notice, and without a key sends no token\n'

# 5. Bad settings fail plainly and never echo content.
expect_failure() {
  # $1 label, $2 expected message, $3 log, rest: command that must fail.
  local label="$1" message="$2" log="$3"
  shift 3
  # The build functions write their own output to $log.
  if "$@"; then
    fail "$label succeeded"
  fi
  grep -qF "$message" "$log" || fail "$label did not print the plain message" "$log"
  grep -qF "NOT-A-VALUE" "$log" && fail "$label output shows the file content"
  return 0
}
ENV_MESSAGE="manijeroEnvironment must be local or qa; prod is not configured."
for value in prod QA ""; do
  expect_failure "manijeroEnvironment=$value" "$ENV_MESSAGE" "$WORK/env.log" setting_build "-PmanijeroEnvironment=$value" "$WORK/env.log" :androidApp:generateDebugBuildConfig
done
expect_failure "an invalid QA address" \
  "qa-address.local is not a valid QA address. Write one https:// address on one line, for example https://qa.example.org" \
  "$WORK/address.log" qa_build "$WORK/invalid-address.local" "$QA_HOME" "$WORK/address.log" :androidApp:generateDebugBuildConfig
printf '%s\n' 'http://qa.example.org' > "$WORK/http-address.local"
expect_failure "a non-https QA address" "is not a valid QA address" "$WORK/http.log" \
  qa_build "$WORK/http-address.local" "$QA_HOME" "$WORK/http.log" :desktopApp:generateEnvironmentResource
mkdir -p "$WORK/bad-qa-home/credentials"
printf '%s\n' "$INVALID_CONTENT" > "$WORK/bad-qa-home/credentials/qa-test-device.token"
KEY_MESSAGE="The QA access key is not valid. Run ./scripts/init.sh --qa-settings-setup again."
expect_failure "an invalid QA key (Android)" "$KEY_MESSAGE" "$WORK/key-android.log" \
  qa_build "$WORK/address.local" "$WORK/bad-qa-home" "$WORK/key-android.log" :androidApp:generateDebugBuildConfig
expect_failure "an invalid QA key (Desktop)" "$KEY_MESSAGE" "$WORK/key-desktop.log" \
  qa_build "$WORK/address.local" "$WORK/bad-qa-home" "$WORK/key-desktop.log" :desktopApp:generatePilotTokenResource
qa_build "$WORK/address.local" "$WORK/bad-qa-home" "$WORK/key-release.log" :androidApp:generateReleaseBuildConfig :desktopApp:jar \
  || fail "the QA release config or the jar failed with an invalid key" "$WORK/key-release.log"
assert_no_secret_outputs
printf 'PASS: a bad environment, address, or key fails with the plain message and no content; release and the jar still build\n'

# 6. Regenerate in local mode, so build/ holds no fake and no QA output.
local_build "$WORK/final.log" "${ANDROID_TASKS[@]}" "${DESKTOP_TASKS[@]}" || fail "the final local build failed" "$WORK/final.log"
regenerated=1
for generated in "$DEBUG_CONFIG" "$RELEASE_CONFIG" "$ENVIRONMENT_RESOURCE" "$DESKTOP_JAR"; do
  if [[ -f "$generated" ]] && grep -aqF "$FAKE_KEY" "$generated"; then
    fail "$generated still holds the fake key"
  fi
done
grep -qF "qa.example.org" "$DEBUG_CONFIG" "$ENVIRONMENT_RESOURCE" && fail "build outputs still hold the fake QA address"
printf 'Result: the environment build check passed; build outputs are back to local and hold no fake.\n'
