# Validation: answer_cache

- Verdict: accept (independent, final per owner decision 7; no owner walkthrough).
- Spec: [answer_cache.md](../specs/answer_cache.md); evidence: [appendix](../specs/answer_cache.appendix.md).

## Checks rerun

- `./scripts/init.sh --feature answer_cache`: 528 passed.
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 2204 passed, 5 skipped).
- `--verify` not rerun: the diff touches only `backend/`, docs, and `feature_list.json` (no `shared/`, apps, Gradle, packaging).

## Review against the owner decisions

- In memory only: `backend/app/answer_cache.py` holds a SHA-256 key and the response; no file, log, or metric write. A test covers question and land text absent from logs, `/metrics`, and disk; a new app starts empty.
- Key: normalized question + land context + knowledge identity + model identity; no fuzzy matching. An identity change empties the cache; TTL 24 h (hit at 23:59:59, expired at 24:00:00).
- Transient outcomes, `generation_error`, and 503 are never stored; `*_used` and extractive results are. Clarification, year pre-check, and corpus validation run before lookup.
- Every hit re-runs `verify_draft` (or the abstention shape check) and discards the entry whole on failure.
- Setting `MANIJERO_ANSWER_CACHE`: on by default, `off` disables, an invalid value logs `value_invalid`; the local settings file passes `off` through.

## Implementer deviations checked

- Vector-search fallback marks the request not cacheable: stricter than the spec, tested, accepted.
- `test_health_metrics` generation tests run with `answer_cache=None` so each request makes the counted draft; cache behavior has its own tests. `test_hybrid_retrieval` uses a fresh cache per test. Neither masks a regression.

## Limits that remain

- Per process (two pilot workers mean two caches), lost on restart, no container setting, a hit has no `inspection`; recorded in `docs/progress/known-limitations.md`.
