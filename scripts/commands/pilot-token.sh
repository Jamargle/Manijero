# Pilot token: --pilot-token-save. Sourced by scripts/init.sh and exits before the toolchain checks.

# Owner command (docs/owner-guide/pilot-token-and-settings.md "Give the apps the pilot token"): save the pilot bearer token
# from the clipboard into the git-ignored pilot-token.local, which the next Android and Desktop builds
# read. It needs no Python, Java, or Android SDK, and never prints the token or its length.
# MANIJERO_CLIPBOARD_CLI and MANIJERO_PILOT_TOKEN_FILE are for tests only (fake tokens).
if [[ "${1:-}" == "--pilot-token-save" ]]; then
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  pilot_token_file="${MANIJERO_PILOT_TOKEN_FILE:-$MANIJERO_ROOT/pilot-token.local}"
  clipboard_cli="${MANIJERO_CLIPBOARD_CLI:-pbpaste}"
  if ! command -v "$clipboard_cli" >/dev/null 2>&1 || ! pilot_token="$("$clipboard_cli" 2>/dev/null)"; then
    printf 'Result: this command could not read the clipboard; it needs a Mac. Ask the developer for help.\n'
    exit 1
  fi
  # Trim surrounding whitespace and line breaks; anything inside stays and is refused below.
  pilot_token="${pilot_token#"${pilot_token%%[![:space:]]*}"}"
  pilot_token="${pilot_token%"${pilot_token##*[![:space:]]}"}"
  if [[ -z "$pilot_token" ]]; then
    printf 'Result: the clipboard is empty. Copy the pilot token first, then run this command again.\n'
    exit 1
  fi
  # Byte-wise check in this shell (the token is never a process argument): 32-512 characters of
  # A-Z a-z 0-9 - . _ ~ + / with optional trailing '=' padding.
  LC_ALL=C
  pilot_token_shape='^[A-Za-z0-9._~+/-]+=*$'
  if (( ${#pilot_token} < 32 || ${#pilot_token} > 512 )) || [[ ! "$pilot_token" =~ $pilot_token_shape ]]; then
    printf 'Result: the clipboard does not hold a pilot token. Copy the whole token again, then run this command again.\n'
    exit 1
  fi
  pilot_token_replaced=0
  [[ -e "$pilot_token_file" ]] && pilot_token_replaced=1
  # Write a private temporary file next to the target, then rename it, so a failure never leaves a
  # half-written token and never touches the previous one.
  if ! pilot_token_tmp="$(mktemp "$(dirname -- "$pilot_token_file")/.pilot-token.XXXXXX" 2>/dev/null)"; then
    printf 'Result: the pilot token could not be saved, and nothing changed. Ask the developer for help.\n'
    exit 1
  fi
  if ! { chmod 600 "$pilot_token_tmp" && printf '%s' "$pilot_token" > "$pilot_token_tmp" && mv -f "$pilot_token_tmp" "$pilot_token_file"; } 2>/dev/null; then
    rm -f "$pilot_token_tmp"
    printf 'Result: the pilot token could not be saved, and nothing changed. Ask the developer for help.\n'
    exit 1
  fi
  if (( pilot_token_replaced )); then
    printf 'Result: the pilot token is saved; it replaced the previous one. The next test build will send it.\n'
  else
    printf 'Result: the pilot token is saved. The next test build will send it.\n'
  fi
  exit 0
fi
