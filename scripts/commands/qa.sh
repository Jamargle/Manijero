# QA service and alerts: --environments-status, --qa-settings-setup, --qa-*, --qa-alerts-*, --qa-check.
# Owner commands for the three environments (docs/owner-guide/pilot-token-and-settings.md "Your environments"): a read-only
# status of local, QA, and prod, and QA settings plus access keys prepared on this computer. Nothing
# is deployed and no server is contacted. MANIJERO_LOCAL_HOME and MANIJERO_QA_HOME are for tests only.
if [[ "${1:-}" == "--environments-status" || "${1:-}" == "--qa-settings-setup" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  if [[ "$1" == "--environments-status" ]]; then
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/environments.py" status
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/environments.py" qa-setup
fi

# Owner commands for the QA answer service on this Mac, reachable over HTTPS through Tailscale Funnel
# (docs/owner-guide/qa.md "Owner walkthrough: QA"). QA is for made-up test questions only. Test-only
# variables: MANIJERO_QA_HOME, MANIJERO_LOCAL_HOME, MANIJERO_DOCKER_CLI, MANIJERO_TAILSCALE_CLI,
# MANIJERO_QA_PORT, and MANIJERO_QA_ADDRESS_FILE.
if [[ "${1:-}" == "--qa-deploy" || "${1:-}" == "--qa-update" || "${1:-}" == "--qa-rollback" || "${1:-}" == "--qa-status" || "${1:-}" == "--qa-stop" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    if [[ "$1" == "--qa-stop" ]]; then
      printf 'Result: QA was not running, so there was nothing to stop.\n'
      exit 0
    fi
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/qa_service.py" "${1#--qa-}"
fi

# Owner commands to send the approved knowledge merged to main to QA, or take QA back to its earlier
# knowledge (docs/owner-guide/qa.md "Send approved knowledge to QA"). Test-only variables are those above
# plus MANIJERO_QA_KNOWLEDGE_REPO, MANIJERO_QA_KNOWLEDGE_DEV_PYTHON, MANIJERO_QA_KNOWLEDGE_HYBRID_PYTHON,
# MANIJERO_QA_KNOWLEDGE_EMBEDDING_CONFIG, MANIJERO_QA_KNOWLEDGE_TODAY, and MANIJERO_QA_PUBLIC_PROBE_URL.
if [[ "${1:-}" == "--qa-knowledge-deploy" || "${1:-}" == "--qa-knowledge-rollback" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    if [[ "$1" == "--qa-knowledge-deploy" ]]; then
      printf 'Result: the approved knowledge was not sent to QA. Run ./scripts/init.sh --local-rag-setup.\n'
    else
      printf "Result: QA's knowledge was not rolled back. Run ./scripts/init.sh --local-rag-setup.\n"
    fi
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/qa_knowledge.py" "${1#--qa-knowledge-}"
fi

# Owner commands for the QA Telegram alerts (a launchd check every 5 minutes on this Mac,
# docs/owner-guide/qa-alerts.md "Set up Telegram alerts"). Test-only variables: MANIJERO_ALERTS_HOME,
# MANIJERO_QA_HOME, MANIJERO_LAUNCHCTL_CLI, MANIJERO_LAUNCH_AGENTS_DIR, MANIJERO_DOCKER_CLI,
# MANIJERO_TAILSCALE_CLI, MANIJERO_QA_PORT, and MANIJERO_TELEGRAM_API (loopback only).
if [[ "${1:-}" == "--qa-alerts-setup" || "${1:-}" == "--qa-alerts-start" || "${1:-}" == "--qa-alerts-stop" || "${1:-}" == "--qa-alerts-status" || "${1:-}" == "--qa-alerts-test" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    if [[ "$1" == "--qa-alerts-stop" ]]; then
      printf 'Result: QA alerts were not on, so there was nothing to stop.\n'
      exit 0
    fi
    if [[ "$1" == "--qa-alerts-status" ]]; then
      printf 'Result: QA alerts are off. Turn them on with ./scripts/init.sh --qa-alerts-start.\n'
      exit 1
    fi
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: setup has not run yet.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/qa_alerts.py" "${1#--qa-alerts-}"
fi

# Owner command: check the QA Desktop app against the live QA service end to end (docs/owner-guide/qa.md
# "Check the QA Desktop app"). Like --local-smoke it resolves Java here and lets qa_check.py report a
# missing one. Test-only variables: MANIJERO_QA_HOME and MANIJERO_QA_ADDRESS_FILE.
if [[ "${1:-}" == "--qa-check" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the QA check did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  manijero_resolve_java || true
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/qa_check.py"
fi
