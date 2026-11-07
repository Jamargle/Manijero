# Validation: official_page_change_monitor

Verdict: **accept** (independent validator; revalidation after repair). Developer-only: validator
acceptance is final, with no owner walkthrough.

Spec: [../specs/official_page_change_monitor.md](../specs/official_page_change_monitor.md) · Evidence:
[appendix](../specs/official_page_change_monitor.appendix.md). Repair: the 2026-11-07 MEDIUM
(missing `Content-Type` accepted as `text/plain`).

## Checks rerun

- `./scripts/init.sh --feature official_page_change_monitor` — **passed**: `50 passed in 0.06s`;
  published block current; suite offline by autouse socket guard.
- `--fast` not rerun (only the repaired module and its focused test changed since its recorded run;
  prior result: 10 offline checks, backend `2089 passed, 5 skipped`); `--verify` not rerun (backend,
  fixtures, and docs only; no `shared/`, apps, Gradle, contracts, or packaging input).
- Probes (`Message`/`HTTPMessage`): absent/empty/whitespace `Content-Type` rejected as `unsupported
  content type`; explicit `text/plain` (any case, charset), `text/html`, and `application/xhtml+xml`
  accepted; PDF/octet-stream rejected; `304` unchanged.
- CLI probe with a stubbed request: missing header fails one page (no snapshot) while the other page
  is `first_seen`; exit `1`; no HTML in the report. Explicit `text/plain` still succeeds.
- `--help` exit `0`. `git status` shows only the expected new module/CLI/tests/fixtures, spec,
  appendix, validation, and three docs; `knowledge/`, `scripts/init.sh`, and `feature_list.json`
  are unchanged.

## Repair verdict

Resolved: `_content_type` returns `""` for absent/empty, `_accept_response` rejects it as
`unsupported content type`, and the new test covers both shapes and asserts no snapshot; the CLI
probe confirms page isolation. No regression in allowed types, `304`, charset, report-before-state,
or path isolation.

## Findings

None blocking. Two low-severity residuals are limits, not requirements:

- **LOW — malformed non-empty `Content-Type` still fails open.** A value without exactly one `/`
  (e.g. `garbage`, `; charset=utf-8`) is coerced to `text/plain` and accepted. The trigger needs an
  invalid header from an approved first-party host; the effect is a noisy operator baseline, not a
  canonical, answer, or legal claim (`document_ingestion.py` has the same stdlib pattern). Optional
  hardening: compare `declared.split(";", 1)[0].strip().lower()` against the allowlist.
- **LOW — relative `knowledge/` from `backend/`.** `--state knowledge/x.json` resolves to
  `backend/knowledge/x.json` (not the canonical root) and is accepted; the canonical directory is
  still refused. A probe artifact was deleted; the accidental live GET (FEGA 404) is not coverage
  evidence.

## Review

- Scenarios 1–3 and 5–7 stay covered (baseline, repeat, deltas/caps, markup-only, last-good across
  failures and `304`, determinism, isolation, `Result:` lines, exits); scenario 4 passes for every
  listed failure class, except the malformed-header case noted above.
- Scope held: stdlib plus `source_catalog`; first-party hosts inside `APPROVED_HOSTS`; no scheduling,
  linked-resource fetch, browser, ingestion, discovery, `/ask`, retrieval, release, index, contract,
  client, or owner-guide change. Docs match the boundary in `ARCHITECTURE.md`, the answers constraint,
  and `backend/README.md`.
- Security: canonical-`knowledge/` and equal-path checks run before requests; raw markup, scripts,
  bodies, and exception text are never stored or printed; failure categories are value-free.

## Handoff and limits

`feature_list.json` says `not_started`; the validator did not edit status or commit. The orchestrator
should persist `accepted` and add the pointer line.

- Normalization is block/whitespace-level, not semantic; dynamic regions can appear as changes.
- No live page content was validated; success is not evidence of currency, validity, or coverage.
- `SequenceMatcher` over up to 5,000 segments can be slow on a pathological page, though bounded.
- State keeps bounded normalized text (operator data outside `knowledge/`), never answerable or committed.
