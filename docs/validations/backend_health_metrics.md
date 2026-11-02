# Validation: backend_health_metrics

Verdict: accept (independent validator; no owner walkthrough, per owner decision in the spec Notes).

Spec: [../specs/backend_health_metrics.md](../specs/backend_health_metrics.md) · Evidence: [appendix](../specs/backend_health_metrics.appendix.md)

## Checks rerun

- `./scripts/init.sh --feature backend_health_metrics`: 469 passed (published focused block is accurate and runs).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 1855 passed, 4 skipped; harness 13 passed).
- `--verify` not rerun: the diff touches only `backend/`, docs and the feature index, no `shared/`, apps, Gradle, or packaging.

## Review

- Scenarios 1-8 map to 24 tests in `backend/tests/test_health_metrics.py`, including label allowlist, unknown route as `other`, and the 500 count.
- Pilot gate: `/metrics` gated with a per-path limiter window, so scrapes do not use the `/ask` allowance; open in `development`.
- Privacy: stdlib exporter, fixed-code labels only, hooks `_safe`-wrapped; no question, land, or client identifiers recorded.
- Docs: ARCHITECTURE, operations constraint, backend README section, and known limitation updated as the spec required.

## Remaining limits

- Counters are per process and reset on restart; no cross-worker aggregation.
- Source-update recency appears only when `MANIJERO_SOURCE_UPDATE_STATE_DIR` is set; it is run recency, not legal freshness.
- Verified in-process only; no live scrape against a running service.
