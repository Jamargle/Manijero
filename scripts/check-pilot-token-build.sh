#!/usr/bin/env bash
# Build-injection check for the pilot bearer token (docs/specs/client_pilot_credentials.md).
#
# Uses only fake tokens in a mktemp -d folder, passed through MANIJERO_PILOT_TOKEN_FILE, so the
# owner's real pilot-token.local is never read by this script. Only test builds may carry the token
# (owner decision 5). It asserts that:
#   - a valid fake reaches the Android debug BuildConfig and the Desktop generated folder;
#   - with that fake present, the Android release BuildConfig has PILOT_TOKEN = null, and the Desktop
#     jar and build/resources/main hold no token resource or characters (scenario 2a);
#   - only the Desktop `run` task gets the folder: its classpath holds it when the task starts (probed
#     without launching the app), and no jar, packaging, or release task depends on it;
#   - an invalid fake fails the debug BuildConfig and the Desktop resource task with the plain message
#     and without its content, while the release BuildConfig and the jar still build without a token;
#   - no file yields PILOT_TOKEN = null in both variants and no Desktop resource.
# It ends by regenerating without the override, so build/ holds no fake. It prints no token.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WORK="$(mktemp -d)"
FAKE_TOKEN="fakeBuildCheckTokenOnly-0123456789abcdefABCDEF+/="
INVALID_CONTENT="fake invalid content NOT-A-TOKEN-7f3a"
TASKS=(:androidApp:generateDebugBuildConfig :androidApp:generateReleaseBuildConfig :desktopApp:generatePilotTokenResource :desktopApp:jar)
DEBUG_CONFIG="androidApp/build/generated/source/buildConfig/debug/com/jamarglex/manijero/BuildConfig.java"
RELEASE_CONFIG="androidApp/build/generated/source/buildConfig/release/com/jamarglex/manijero/BuildConfig.java"
GENERATED_RESOURCE="desktopApp/build/generated/pilotToken/manijero/pilot-token.txt"
MAIN_RESOURCE="desktopApp/build/resources/main/manijero/pilot-token.txt"
DESKTOP_JAR="desktopApp/build/libs/desktopApp.jar"
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
  # $1: token file, $2: log file, rest: Gradle arguments.
  local token_file="$1" log="$2"
  shift 2
  MANIJERO_PILOT_TOKEN_FILE="$token_file" ./gradlew --quiet "$@" >"$log" 2>&1
}

# Release outputs must hold no token resource and no fake characters.
assert_release_outputs_clean() {
  grep -qF "String PILOT_TOKEN = null;" "$RELEASE_CONFIG" || fail "release BuildConfig does not set PILOT_TOKEN = null"
  grep -qF "$FAKE_TOKEN" "$RELEASE_CONFIG" && fail "release BuildConfig holds the fake token"
  grep -qF "NOT-A-TOKEN" "$RELEASE_CONFIG" && fail "release BuildConfig holds the invalid file's content"
  [[ ! -e "$MAIN_RESOURCE" ]] || fail "$MAIN_RESOURCE exists, so packaged apps would carry the token"
  [[ -f "$DESKTOP_JAR" ]] || fail "$DESKTOP_JAR was not built"
  unzip -l "$DESKTOP_JAR" | grep -qF "pilot-token" && fail "the Desktop jar contains a pilot-token entry"
  unzip -p "$DESKTOP_JAR" | grep -aqF "$FAKE_TOKEN" && fail "the Desktop jar contains the fake token"
  unzip -p "$DESKTOP_JAR" | grep -aqF "NOT-A-TOKEN" && fail "the Desktop jar contains the invalid file's content"
  return 0
}

# 1. A valid fake reaches the test builds only.
printf '%s\n' "$FAKE_TOKEN" > "$WORK/valid.local"
gradle_with "$WORK/valid.local" "$WORK/valid.log" "${TASKS[@]}" || fail "the build with a valid fake token failed" "$WORK/valid.log"
grep -qF "String PILOT_TOKEN = \"$FAKE_TOKEN\";" "$DEBUG_CONFIG" || fail "debug BuildConfig does not hold the fake token"
[[ -f "$GENERATED_RESOURCE" && "$(cat "$GENERATED_RESOURCE")" == "$FAKE_TOKEN" ]] || fail "the Desktop generated folder does not hold the fake token"
grep -qF "$FAKE_TOKEN" "$WORK/valid.log" && fail "the build output shows the token"
printf 'PASS: a valid fake token reaches the Android debug BuildConfig and the Desktop generated folder\n'
assert_release_outputs_clean
printf 'PASS: with the valid fake present, release PILOT_TOKEN is null and the Desktop jar and main resources hold no token\n'

# 2. Only the Desktop run task gets the folder. The probe init script runs the run task's own
#    preparation (including its classpath append) and stops just before the JVM would start, so no
#    window opens. It prints only yes/no facts, never the token.
cat > "$WORK/run-probe.init.gradle" <<'GROOVY'
gradle.taskGraph.whenReady { graph ->
    def run = graph.allTasks.find { it.path == ':desktopApp:run' }
    if (run == null) return
    run.actions.add(run.actions.size() - 1, { task ->
        def folder = task.project.layout.buildDirectory.dir('generated/pilotToken').get().asFile.canonicalFile
        def onClasspath = task.classpath.files.any { it.canonicalFile == folder }
        def hasResource = new File(folder, 'manijero/pilot-token.txt').isFile()
        println "PILOT_RUN_PROBE classpath=${onClasspath ? 'yes' : 'no'} resource=${hasResource ? 'yes' : 'no'}"
        throw new StopExecutionException()
    } as Action)
}
GROOVY
gradle_with "$WORK/valid.local" "$WORK/run-probe.log" --no-configuration-cache -I "$WORK/run-probe.init.gradle" :desktopApp:run \
  || fail "the run-task probe failed" "$WORK/run-probe.log"
grep -qF "PILOT_RUN_PROBE classpath=yes resource=yes" "$WORK/run-probe.log" || fail "the run task's classpath does not hold the token folder" "$WORK/run-probe.log"
grep -qF "$FAKE_TOKEN" "$WORK/run-probe.log" && fail "the run probe output shows the token"
./gradlew --dry-run :desktopApp:jar :desktopApp:createDistributable :desktopApp:createReleaseDistributable \
  :desktopApp:runDistributable :desktopApp:runRelease >"$WORK/packaging.log" 2>&1 || fail "the packaging dry run failed" "$WORK/packaging.log"
grep -qF "generatePilotTokenResource" "$WORK/packaging.log" && fail "a jar, packaging, or release task depends on the token folder"
printf 'PASS: only the Desktop run task has the token folder on its classpath; jar and packaging tasks never depend on it\n'

# 3. An invalid fake fails the test builds without showing its content; release builds are unaffected.
printf '%s\n' "$INVALID_CONTENT" > "$WORK/invalid.local"
for task in :androidApp:generateDebugBuildConfig :desktopApp:generatePilotTokenResource; do
  log="$WORK/invalid${task//:/-}.log"
  if gradle_with "$WORK/invalid.local" "$log" "$task"; then
    fail "$task succeeded with an invalid token file"
  fi
  grep -qF "$MESSAGE" "$log" || fail "$task did not print the plain message" "$log"
  grep -qF "NOT-A-TOKEN" "$log" && fail "$task output shows the token file's content"
done
gradle_with "$WORK/invalid.local" "$WORK/invalid-release.log" :androidApp:generateReleaseBuildConfig :desktopApp:jar \
  || fail "the release BuildConfig or the jar failed with an invalid token file" "$WORK/invalid-release.log"
assert_release_outputs_clean
printf 'PASS: an invalid fake fails the test builds without showing its content; release BuildConfig and the jar still build without it\n'

# 4. No token file: PILOT_TOKEN is null in both variants and there is no Desktop resource.
gradle_with "$WORK/missing.local" "$WORK/missing.log" "${TASKS[@]}" || fail "the build without a token file failed" "$WORK/missing.log"
for config in "$DEBUG_CONFIG" "$RELEASE_CONFIG"; do
  grep -qF "String PILOT_TOKEN = null;" "$config" || fail "$config does not set PILOT_TOKEN = null"
done
for resource in "$GENERATED_RESOURCE" "$MAIN_RESOURCE"; do
  [[ ! -e "$resource" ]] || fail "$resource exists without a token file"
done
printf 'PASS: without a token file PILOT_TOKEN is null in both variants and there is no Desktop resource\n'

# 5. Regenerate without the override, so build/ holds no fake.
env -u MANIJERO_PILOT_TOKEN_FILE ./gradlew --quiet "${TASKS[@]}" >"$WORK/final.log" 2>&1 \
  || fail "the final build without the override failed" "$WORK/final.log"
regenerated=1
for generated in "$DEBUG_CONFIG" "$RELEASE_CONFIG" "$GENERATED_RESOURCE" "$DESKTOP_JAR"; do
  if [[ -f "$generated" ]] && grep -aqF "$FAKE_TOKEN" "$generated"; then
    fail "$generated still holds the fake token"
  fi
done
printf 'Result: the pilot token build check passed; build outputs hold no fake token.\n'
