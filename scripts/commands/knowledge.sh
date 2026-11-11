# Knowledge review, evaluation data, and local evaluation models: --knowledge-updates-*, --knowledge-review-*,
# --golden-*, --trap-*, --glossary-*, --colloquial-*, --grounding-judge-*, --reranker-*, --usability-record.
# Owner commands for the scheduled knowledge update cycle (a launchd run every day at 10:20 on this Mac,
# docs/owner-guide/knowledge-updates.md). Test-only variables: MANIJERO_KNOWLEDGE_OPS_HOME,
# MANIJERO_KNOWLEDGE_OPS_STEP_CLI, MANIJERO_KNOWLEDGE_OPS_NO_WAIT, MANIJERO_LAUNCHCTL_CLI, and MANIJERO_LAUNCH_AGENTS_DIR.
if [[ "${1:-}" == "--knowledge-updates-on" || "${1:-}" == "--knowledge-updates-off" || "${1:-}" == "--knowledge-updates-run" || "${1:-}" == "--knowledge-updates-status" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    if [[ "$1" == "--knowledge-updates-off" ]]; then
      printf 'Result: knowledge updates were not on, so there was nothing to turn off.\n'
      exit 0
    fi
    printf 'The backend tools are not set up yet. Run ./scripts/init.sh --local-rag-setup, then try again.\n'
    printf 'Result: knowledge updates did not run because the backend tools are not set up.\n'
    exit 2
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/knowledge_ops.py" "${1#--knowledge-updates-}"
fi

# Owner commands for hosted knowledge review pull requests (docs/owner-guide/knowledge-review-pull-requests.md).
# Test-only variables: MANIJERO_KNOWLEDGE_REVIEW_HOME, MANIJERO_GH_CLI, and MANIJERO_HOSTED_REVIEW_REPO.
if [[ "${1:-}" == "--knowledge-review-open" || "${1:-}" == "--knowledge-review-protect" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The backend tools are not set up yet. Run ./scripts/init.sh --local-rag-setup, then try again.\n'
    printf 'Result: the knowledge review command did not run because the backend tools are not set up.\n'
    exit 2
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/hosted_review.py" "${1#--knowledge-review-}"
fi

# Owner commands: review the golden questions (docs/owner-guide/golden-set-review.md). --golden-review lists the
# waiting drafts; --golden-decide approve|reject "<name>" <number-or-id>... records a named
# reviewer's decision. Both end with one Result: line and run before the local.properties write.
if [[ "${1:-}" == "--golden-review" || "${1:-}" == "--golden-decide" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  GOLDEN_COMMAND="${1#--golden-}"
  shift
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the golden review did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  if [[ "$GOLDEN_COMMAND" == "review" ]]; then
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/golden_review.py" list "$@"
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/golden_review.py" decide -- "$@"
fi

# Owner commands: review the trap questions (docs/owner-guide/trap-set-review.md). --trap-review lists the
# waiting drafts; --trap-decide approve|reject "<name>" <number-or-id>... records a named
# reviewer's decision. Both end with one Result: line and run before the local.properties write.
if [[ "${1:-}" == "--trap-review" || "${1:-}" == "--trap-decide" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  TRAP_COMMAND="${1#--trap-}"
  shift
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the trap review did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  if [[ "$TRAP_COMMAND" == "review" ]]; then
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/trap_review.py" list "$@"
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/trap_review.py" decide -- "$@"
fi

# Owner commands: review the question glossary (docs/owner-guide/question-glossary-review.md). --glossary-review
# lists the word pairs that wait for a decision; --glossary-decide approve|reject "<name>" <number-or-id>...
# records a named reviewer's decision. Both end with one Result: line and run before the local.properties write.
if [[ "${1:-}" == "--glossary-review" || "${1:-}" == "--glossary-decide" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  GLOSSARY_COMMAND="${1#--glossary-}"
  shift
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the glossary review did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  if [[ "$GLOSSARY_COMMAND" == "review" ]]; then
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/glossary_review.py" list "$@"
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/glossary_review.py" decide -- "$@"
fi

# Owner commands: review the colloquial variants (docs/owner-guide/colloquial-variants-review.md).
# --colloquial-review lists the variants that wait for a decision; --colloquial-decide
# approve|reject "<name>" <number-or-id>... records a named reviewer's decision. Both end with
# one Result: line and run before the local.properties write.
if [[ "${1:-}" == "--colloquial-review" || "${1:-}" == "--colloquial-decide" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  COLLOQUIAL_COMMAND="${1#--colloquial-}"
  shift
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the colloquial variant review did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  if [[ "$COLLOQUIAL_COMMAND" == "review" ]]; then
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/colloquial_ab.py" list "$@"
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/colloquial_ab.py" decide -- "$@"
fi

# Owner commands: the offline grounding judge (docs/owner-guide/grounding-judge.md). --grounding-judge-setup
# downloads the pinned judge model and checks its digest; --grounding-judge-report drafts the reviewed and
# golden questions with the local drafting model, has the judge model check each sentence, and writes
# build/grounding-judge/report.json. Both take no arguments, end with one Result: line, and run before the
# local.properties write.
if [[ "${1:-}" == "--grounding-judge-setup" || "${1:-}" == "--grounding-judge-report" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  GROUNDING_COMMAND="${1#--grounding-judge-}"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the grounding judge command did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  if [[ "$GROUNDING_COMMAND" == "setup" ]]; then
    exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/judge_grounding.py" setup
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/judge_grounding.py" run \
    --catalog "$REPO_ROOT/knowledge/source_catalog.json" \
    --passages "$REPO_ROOT/knowledge/passages.json" \
    --cases "$REPO_ROOT/knowledge/pac_answer_eval.json" \
    --golden "$REPO_ROOT/knowledge/golden_set.json" \
    --active-campaign 2026 \
    --as-of "$(date +%Y-%m-%d)" \
    --report "$REPO_ROOT/build/grounding-judge/report.json"
fi

# Owner commands: the optional local reranker (docs/owner-guide/reranker.md). --reranker-download downloads the
# reranker model and checks it against the reviewed copy; --reranker-measure compares it with today's hybrid search
# on the golden and trap questions and prints the on/off verdict; --reranker-on and --reranker-off write the setting.
# None takes an argument; each ends with one Result: line and runs before the local.properties write. They run in
# the hybrid environment (the one --local-rag-setup builds), which today's search needs.
if [[ "${1:-}" == "--reranker-download" || "${1:-}" == "--reranker-measure" || "${1:-}" == "--reranker-on" || "${1:-}" == "--reranker-off" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  RERANKER_COMMAND="${1#--reranker-}"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  RERANKER_PYTHON="$REPO_ROOT/backend/.venv-hybrid/bin/python"
  if [[ ! -x "$RERANKER_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" hybrid --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the reranker command did not run. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  case "$RERANKER_COMMAND" in
    on|off) exec "$RERANKER_PYTHON" "$REPO_ROOT/backend/scripts/reranker.py" switch "$RERANKER_COMMAND" ;;
    *) exec "$RERANKER_PYTHON" "$REPO_ROOT/backend/scripts/reranker.py" "$RERANKER_COMMAND" ;;
  esac
fi

# Owner command: save one usability-session participant's results under an anonymous code
# (docs/owner-guide/usability-session.md, docs/usability-session/). It never reads or writes the apps or the
# service; the results file lives outside the checkout.
if [[ "${1:-}" == "--usability-record" ]]; then
  REPO_ROOT="$MANIJERO_ROOT"
  if (( $# > 1 )); then
    printf 'Run %s on its own, with nothing after it.\n' "$1" >&2
    exit 2
  fi
  LOCAL_RAG_PYTHON="$REPO_ROOT/backend/.venv/bin/python"
  if [[ ! -x "$LOCAL_RAG_PYTHON" ]] && ! "$REPO_ROOT/scripts/python-env.sh" dev --if-present >/dev/null 2>&1; then
    printf 'The local answer tools are not set up yet. Run ./scripts/init.sh --local-rag-setup to set them up.\n'
    printf 'Result: the usability results were not recorded. Run ./scripts/init.sh --local-rag-setup.\n'
    exit 1
  fi
  exec "$LOCAL_RAG_PYTHON" "$REPO_ROOT/backend/scripts/usability_record.py"
fi
