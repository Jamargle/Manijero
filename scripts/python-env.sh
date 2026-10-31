#!/usr/bin/env bash
# Shared backend Python environments for the base checkout and every git worktree.
#
# Each environment is keyed by its profile, its requirement files, and the base
# interpreter version, and is built once under the repository's git common directory.
# Worktrees then reuse it instead of reinstalling. backend/.venv (dev) and
# backend/.venv-hybrid (hybrid) become symlinks to it, so every published
# "MANIJERO_PYTHON=backend/.venv/bin/python" command keeps working unchanged.
#
# Usage: scripts/python-env.sh [dev|hybrid] [--if-present]
#   dev          runtime + test dependencies (default)
#   hybrid       dev plus the optional torch/transformers/chromadb runtime (several GB)
#   --if-present only link an environment that is already built; never install
#
# MANIJERO_BASE_PYTHON  interpreter to build from (default: newest python3.1x >= 3.10 on PATH)
# MANIJERO_VENV_ROOT    where environments live (default: <git common dir>/manijero-venvs)
set -euo pipefail

MIN_MINOR=10
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

profile="dev"
if_present=0
for arg in "$@"; do
  case "$arg" in
    dev|hybrid) profile="$arg" ;;
    --if-present) if_present=1 ;;
    *) printf 'Usage: scripts/python-env.sh [dev|hybrid] [--if-present]\n' >&2; exit 2 ;;
  esac
done

case "$profile" in
  dev)
    requirement_files=(requirements.txt requirements-dev.txt)
    link="$BACKEND_DIR/.venv"
    ;;
  hybrid)
    requirement_files=(requirements.txt requirements-embeddings.txt requirements-hybrid.txt requirements-dev.txt)
    link="$BACKEND_DIR/.venv-hybrid"
    ;;
esac

# Prints the first interpreter at or above 3.$MIN_MINOR.
base_python() {
  local candidate
  for candidate in "${MANIJERO_BASE_PYTHON:-}" python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]] || continue
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, $MIN_MINOR) else 1)" >/dev/null 2>&1; then
      "$candidate" -c 'import sys; print(sys.executable)'
      return 0
    fi
  done
  return 1
}

# Warns when the interpreter lives inside a worktree: removing that worktree would
# break every environment built from it.
warn_if_inside_worktree() {
  local real="$1" path
  while IFS= read -r path; do
    if [[ "$real" == "$path"/* ]]; then
      printf 'Warning: base interpreter %s lives inside the worktree %s.\n' "$real" "$path" >&2
      printf '         Removing that worktree breaks these environments; set MANIJERO_BASE_PYTHON to an interpreter outside the repository.\n' >&2
    fi
  done < <(git -C "$REPO_ROOT" worktree list --porcelain | sed -n 's/^worktree //p')
}

common_dir="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)"
venv_root="${MANIJERO_VENV_ROOT:-$common_dir/manijero-venvs}"

if ! python="$(base_python)"; then
  printf 'The backend needs Python 3.%s or newer, and none was found on PATH.\n' "$MIN_MINOR" >&2
  printf 'Install one (for example: brew install python@3.12) or set MANIJERO_BASE_PYTHON.\n' >&2
  exit 1
fi
real_python="$("$python" -c 'import os, sys; print(os.path.realpath(sys.executable))')"
version="$("$python" -c 'import platform; print(platform.python_version())')"

key="$(
  {
    printf '%s %s\n' "$profile" "$version"
    for file in "${requirement_files[@]}"; do
      printf '== %s\n' "$file"
      cat "$BACKEND_DIR/$file"
    done
  } | shasum -a 256 | cut -c1-12
)"
env_dir="$venv_root/$profile-py$version-$key"

link_env() {
  if [[ -e "$link" && ! -L "$link" ]]; then
    printf 'Shared environment ready at %s, but %s is a local directory; it was left untouched.\n' "$env_dir" "${link#"$REPO_ROOT"/}" >&2
    printf 'Rename or remove it, then rerun to use the shared environment.\n' >&2
    return 0
  fi
  ln -sfn "$env_dir" "$link"
  printf '%s -> %s\n' "${link#"$REPO_ROOT"/}" "$env_dir"
}

if [[ -f "$env_dir/.complete" ]]; then
  link_env
  exit 0
fi
if (( if_present )); then
  exit 1
fi

warn_if_inside_worktree "$real_python"
mkdir -p "$venv_root"

# One builder at a time: concurrent worktree sessions wait instead of racing.
lock="$env_dir.lock"
waited=0
until mkdir "$lock" 2>/dev/null; do
  if [[ -f "$env_dir/.complete" ]]; then
    link_env
    exit 0
  fi
  if (( waited >= 900 )); then
    printf 'Timed out waiting for %s. If no build is running, remove that directory and rerun.\n' "$lock" >&2
    exit 1
  fi
  sleep 2
  waited=$((waited + 2))
done
trap 'rmdir "$lock" 2>/dev/null || true' EXIT

if [[ ! -f "$env_dir/.complete" ]]; then
  # A directory without the marker is a build that did not finish.
  rm -rf "$env_dir"
  printf 'Building shared %s environment with Python %s in %s\n' "$profile" "$version" "$env_dir"
  "$python" -m venv "$env_dir"
  pip_args=()
  for file in "${requirement_files[@]}"; do
    pip_args+=(-r "$BACKEND_DIR/$file")
  done
  "$env_dir/bin/python" -m pip install --disable-pip-version-check --quiet "${pip_args[@]}"
  printf '%s\n' "$real_python" > "$env_dir/.complete"
fi
link_env
