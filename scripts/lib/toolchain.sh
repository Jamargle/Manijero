# Android SDK, local.properties, Gradle wrapper, and Java for every mode that is not handled above.
# Auto-detect ANDROID_HOME and local.properties if not already set
# Works from any subdirectory (including git worktrees)
if [[ -z "${ANDROID_HOME:-}" && -z "${ANDROID_SDK_ROOT:-}" ]]; then
  # Try common macOS locations
  ANDROID_HOME="$HOME/Library/Android/sdk"
  ANDROID_SDK_ROOT="$ANDROID_HOME"
fi
ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"

# Ensure local.properties exists in current directory with SDK path
# This handles git worktrees correctly - each worktree gets its own file
if [[ ! -f "local.properties" ]]; then
  cat > local.properties <<EOF
sdk.dir=$ANDROID_HOME
EOF
  echo "Created local.properties with SDK path: $ANDROID_HOME"
fi

# Avoid conflicting AGP location environment variables
unset ANDROID_PREFS_ROOT

# Export environment variables for Gradle
export ANDROID_HOME
export ANDROID_SDK_ROOT

REPO_ROOT="$MANIJERO_ROOT"
cd "$REPO_ROOT"

if [[ ! -x "$REPO_ROOT/gradlew" ]]; then
  printf 'Gradle wrapper is missing or not executable: %s/gradlew\n' "$REPO_ROOT" >&2
  exit 1
fi

if ! manijero_resolve_java; then
  printf '%s\n' "$MANIJERO_JAVA_MISSING"
  printf 'Result: nothing was run. Install Temurin 21 from https://adoptium.net, then run this command again.\n'
  exit 1
fi
