# shellcheck shell=bash
# The one Java resolution for every ./scripts/init.sh path that runs ./gradlew or java. It is
# sourced by init.sh, never run on its own, and works with the macOS bash 3.2.
#
# manijero_resolve_java picks the first of:
#   (a) JAVA_HOME, when its bin/java runs;
#   (b) /usr/libexec/java_home -v 21, when it answers and that bin/java runs;
#   (c) a java on PATH that runs (`java -version` succeeds, so Apple's /usr/bin/java placeholder,
#       which only prints "Unable to locate a Java Runtime", is rejected);
#   (d) the newest JDK 21 Gradle downloaded under ${GRADLE_USER_HOME:-$HOME/.gradle}/jdks (one or
#       two folders down), chosen by its version (from the JDK's `release` file, never by date), in
#       both <dir>/Contents/Home and <dir> layouts.
# On success it exports JAVA_HOME and puts $JAVA_HOME/bin first on PATH, and returns 0. Otherwise
# it unsets JAVA_HOME and returns 1. Probing never prints: the placeholder's message is discarded.
#
# MANIJERO_JAVA_HOME_TOOL replaces /usr/libexec/java_home, for tests only.

MANIJERO_JAVA_MISSING='Java was not found on this computer. Install Temurin 21 from https://adoptium.net, then run this command again.'

manijero_java_runs() {
  [[ -n "${1:-}" && -x "$1" ]] && "$1" -version >/dev/null 2>&1
}

# The java.home a working java reports, or the directory above its bin/.
manijero_java_home_of() {
  local java="$1" home real
  home="$("$java" -XshowSettings:properties -version 2>&1 | awk -F'= ' '/^[[:space:]]*java\.home =/ { print $2; exit }')"
  if [[ -n "$home" && -d "$home" ]]; then
    printf '%s\n' "$home"
    return 0
  fi
  real="$java"
  while [[ -L "$real" ]]; do
    local link
    link="$(readlink "$real")"
    case "$link" in
      /*) real="$link" ;;
      *) real="$(dirname -- "$real")/$link" ;;
    esac
  done
  (cd -- "$(dirname -- "$real")/.." && pwd)
}

# The JAVA_VERSION of a JDK home (for example 21.0.5), without any +build suffix; empty if unknown.
manijero_jdk_version() {
  local release="$1/release" version=""
  if [[ -f "$release" ]]; then
    version="$(sed -n 's/^JAVA_VERSION="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$release" | head -n 1)"
  fi
  printf '%s\n' "${version%%[+_-]*}"
}

# The newest JDK 21 home under the Gradle-downloaded JDK folder, or nothing.
manijero_newest_gradle_jdk21() {
  local jdks="${GRADLE_USER_HOME:-$HOME/.gradle}/jdks" dir home version
  [[ -d "$jdks" ]] || return 1
  {
    # Gradle keeps either <jdks>/<jdk> or <jdks>/<vendor>/<jdk>; each may be a macOS bundle.
    for dir in "$jdks"/*/ "$jdks"/*/*/; do
      [[ -d "$dir" ]] || continue
      dir="${dir%/}"
      if [[ -x "$dir/Contents/Home/bin/java" ]]; then
        home="$dir/Contents/Home"
      elif [[ -x "$dir/bin/java" ]]; then
        home="$dir"
      else
        continue
      fi
      version="$(manijero_jdk_version "$home")"
      case "$version" in
        21|21.*) ;;
        *) continue ;;
      esac
      manijero_java_runs "$home/bin/java" || continue
      # Pad to four numeric fields so `sort` compares by version.
      printf '%s\t%s\n' "$(printf '%s.0.0.0' "$version" | awk -F. '{ printf "%05d.%05d.%05d.%05d", $1, $2, $3, $4 }')" "$home"
    done
  } | sort | tail -n 1 | cut -f 2-
}

manijero_resolve_java() {
  local candidate tool="${MANIJERO_JAVA_HOME_TOOL:-/usr/libexec/java_home}" path_java
  candidate=""
  if [[ -n "${JAVA_HOME:-}" ]] && manijero_java_runs "$JAVA_HOME/bin/java"; then
    candidate="$JAVA_HOME"
  fi
  if [[ -z "$candidate" && -x "$tool" ]]; then
    local from_tool
    from_tool="$("$tool" -v 21 2>/dev/null || true)"
    if [[ -n "$from_tool" ]] && manijero_java_runs "$from_tool/bin/java"; then
      candidate="$from_tool"
    fi
  fi
  if [[ -z "$candidate" ]]; then
    path_java="$(command -v java 2>/dev/null || true)"
    if [[ -n "$path_java" ]] && manijero_java_runs "$path_java"; then
      candidate="$(manijero_java_home_of "$path_java")"
      manijero_java_runs "$candidate/bin/java" || candidate=""
    fi
  fi
  if [[ -z "$candidate" ]]; then
    candidate="$(manijero_newest_gradle_jdk21 || true)"
  fi
  if [[ -z "$candidate" ]]; then
    unset JAVA_HOME
    return 1
  fi
  JAVA_HOME="$candidate"
  PATH="$JAVA_HOME/bin:$PATH"
  export JAVA_HOME PATH
  return 0
}
