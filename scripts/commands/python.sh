# Python environment passthrough: --setup-python (scripts/python-env.sh). Exits before the toolchain checks.
# The backend is independent of the Android/Gradle toolchain. Handle it before
# the Android SDK and Java setup below, so it can be started on its own.
if [[ "${1:-}" == "--setup-python" ]]; then
  shift
  exec "$SCRIPTS_DIR/python-env.sh" "$@"
fi
