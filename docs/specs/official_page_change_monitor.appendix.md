# `official_page_change_monitor` — appendix

## Repository research

### Files inspected

- `AGENTS.md`, `PROGRESS.md` Current state — repository routing, known limits, and the accepted monitoring/discovery/scheduler context; no page-change monitor exists.
- `ARCHITECTURE.md` runtime surfaces — `source_monitor.py`, `source_discovery.py`, and `change_impact.py` are operator-side components; a page monitor must join that layer and stay out of the answer service.
- `docs/constraints/answers-and-knowledge.md` — knowledge updates write quarantined candidates only, change-impact analysis is read-only, and nothing becomes answerable without human approval; page monitoring is a review signal.
- `docs/constraints/operations.md` — owner operations need named commands and plain result lines; this feature is developer-only, so it adds no owner mode, guide step, or walkthrough.
- `backend/app/source_monitor.py` — exact approved-host validation, same-host HTTPS redirects, 15-second timeout, 5 MiB cap, exact-byte SHA-256, atomic `source-monitor-state-v1`, and fixed value-free failure strings; the pattern to follow for bounds and fail-closed behavior.
- `backend/app/source_catalog.py` — `APPROVED_HOSTS` and `ISSUER_ALLOWED_HOSTS`; FEGA, MAPA, and Junta first-party host pairs are already approved.
- `backend/app/document_ingestion.py` — a stdlib `HTMLParser` extractor, charset fallback, and text bounds already exist, but they are coupled to candidate identity/quarantine; do not reuse wholesale or create candidates here.
- `backend/tests/test_source_monitor.py`, `backend/tests/test_document_ingestion.py` — offline request seams, fake responses, and fixture-based failure tests; the new suite can follow the same shape.
- `backend/scripts/scan_official_sources.py`, `backend/scripts/discover_official_sources.py` — thin CLIs with documented exit codes; the current monitor writes JSON to stdout, while this feature writes a JSON report and prints plain `Result:` lines.
- `scripts/init.sh` — `--backend-tests [targets]` runs a focused pytest target from `backend/`, and `--feature` executes the spec's verify block unchanged; no new init mode is required.
- `backend/README.md` lines 1271-1342 — the accepted manual-monitoring documentation pattern: config shape, command, state path, exit codes, bounds, and honest limits.
- `backend/tests/fixtures/` — the existing fixture layout; page fixtures can be small synthetic HTML files under a new `page_monitor/` directory.
- `docs/specs/official_source_monitoring.md` and its archived appendix — accepted contract and evidence shape for a bounded monitor.
- `docs/specs/legal_change_impact_analysis.md` and `backend/app/change_impact.py` — legal interpretation is a separate read-only feature over quarantined documents; it must not be merged into page monitoring.
- `knowledge/source_catalog.json` — four approved legal documents; it contains no FEGA/MAPA/Junta PAC landing-page URLs.
- `feature_list.json` — `official_page_change_monitor` is `not_started` and depends on `official_source_monitoring`; exact status stays with the selector.

### Existing patterns to follow

- Standard library only: `urllib`, `html.parser`, `difflib`, `hashlib`, `json`, and `pathlib`; no new runtime dependency.
- Exact host validation against `source_catalog.py`; no new host or issuer; same-host HTTPS redirects only.
- Bounded requests and text; fixed failure categories; never persist raw response bodies, arbitrary exception text, or script content.
- Injectable request and clock seams so every test stays offline.
- Atomic, versioned JSON artifacts with strict shape validation before use.
- One thin CLI with stable exit codes and one plain-language result line per page plus a summary.

### Current gaps

- No page-monitor module, CLI, fixtures, or page URL config exists in the checkout.
- `source_monitor.py` covers RSS/Atom/JSON feeds only; it hashes whole feed responses but does not extract or diff visible page text.
- `document_ingestion.py` HTML extraction is candidate-coupled and writes quarantine state; reusing it would blur the discovery/ingestion boundary.
- There is no committed list of PAC page URLs; the developer supplies an explicit config, and no live page or URL path was verified during planning.
- `ISSUER_ALLOWED_HOSTS` includes BOE hosts for FEGA and MAPA; this feature narrows page hosts to each issuer's first-party pair.
- The state keeps the last bounded normalized visible text outside `knowledge/` only so the next run can diff; it is operator data, never canonical or answerable, and must not be committed.
- Detection quality is unmeasured; dynamic navigation, dates, and personalization can produce noise even with normalized text.
- No scheduler or alert path exists here by owner decision; a later feature would have to compose this command explicitly.

## Implementation plan

1. Create `backend/app/page_monitor.py` with schema/version constants, `PageMonitorError`, the issuer-to-first-party-host map, and strict config validation.
2. Add the bounded fetch seam: HTTPS only, 15-second timeout, 5 MiB cap, same-host redirects, conditional validators, and accepted `200`/`304` plus `text/html`, `application/xhtml+xml`, and `text/plain` for `200`.
3. Add HTML/plain-text extraction with `html.parser`, charset fallback, visible-block segmentation, deterministic `NFKC` whitespace normalization, and segment/character bounds.
4. Add exact-byte and normalized-text SHA-256 plus a `difflib.SequenceMatcher(autojunk=False)` diff that classifies `changed`, `added`, and `removed` with full counts and capped excerpts.
5. Add strict `official-page-monitor-state-v1` read/validate/write and deterministic `official-page-change-report-v1` build/write, with atomic replacement and refusal under `knowledge/` or for equal paths.
6. Add the command runner and `Result:` lines; make `backend/scripts/monitor_official_pages.py` a thin wrapper with exit `0`/`1`/`2`.
7. Add synthetic fixtures and `backend/tests/test_page_monitor.py` covering config, hosts, redirects, content types, bounds, normalization, diffs, last-good state, `304`, determinism, path isolation, and command output.
8. Update `ARCHITECTURE.md`, `docs/constraints/answers-and-knowledge.md`, and `backend/README.md`; run focused and full offline checks; append evidence here.

## Verification plan

- `./scripts/init.sh --backend-tests tests/test_page_monitor.py -q` — all focused page-monitor tests pass with no network access.
- `./scripts/init.sh --fast` — the full offline tier still passes before acceptance (recommended evidence; no live upstream request).
- Determinism check — two runs with the same config, fixture bytes, prior state, and `--now` produce byte-identical reports.
- Isolation check — `git diff` after a run shows no `knowledge/`, `/ask`, retrieval, release, index, client, or owner-guide change; state/report live outside `knowledge/`.
- Manual check, optional and read-only — a developer may run the command against one configured page; record the URL and time, use a disposable state/report path, and do not treat success as legal currency or coverage.
- E2E: none. This is a developer-only backend command with no app UI, HTTP API, authentication, routing, or persistent client flow; injected-fetch unit/integration coverage is sufficient. A later scheduler or orchestrator feature would own any end-to-end composition.

## Evidence to capture

- Focused and full backend command results, with the test count and offline status.
- Config, state, and report shapes (synthetic only), including the schema versions and atomic write behavior.
- Tests for unapproved/lookalike hosts, credential/fragment/root/port URLs, cross-host redirects, content types, timeouts, size/text bounds, empty text, first/unchanged/changed/markup-only outcomes, `304`, failure retention, and deterministic output.
- A socket-blocking guard proving the focused suite never opens a network connection.
- A recorded `Result:`/exit-code matrix for all-success, mixed failure, and config/path error.
- Proof that a run leaves `knowledge/`, canonical catalog/passages, releases, indexes, `/ask`, and retrieval untouched.
- Honest limits: whitespace/block normalization is not semantic diffing; dynamic page regions can create noise; no live PAC URL was verified; no legal-currency, validity, coverage, or answer-quality claim is made.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

### 2026-11-07 — implementer

- `./scripts/init.sh --backend-tests tests/test_page_monitor.py -q` — `48 passed in 0.08s`; autouse socket guard proves the focused suite stays offline.
- `./scripts/init.sh --feature official_page_change_monitor` — focused tier passed (`48 passed`).
- `./scripts/init.sh --fast` — all 10 offline checks passed; backend suite `2089 passed, 5 skipped`.
- `python3 backend/scripts/monitor_official_pages.py --help` — exit `0`; the named command loads without a request.
- Manual unsafe-destination run with a temporary config/state/report — exit `1`, `Result: fega-pac: could not be checked (upstream request failed).`, no network because the URL is rejected before fetch.
- Manual run with `--state knowledge/should-not-exist.json` — exit `2`, `knowledge untouched`.
- `git status --short` after verification — only the new module/CLI/tests/fixtures and the three required docs changed; no `knowledge/`, `contracts/`, `shared/`, client, or owner-guide change.
- Determinism and isolation tests: two runs with the same config, bytes, prior state, and `--now` produce byte-identical reports sorted by id; state/report are refused under `knowledge/` or when equal; report is written before state and a state write failure leaves last-good state intact.
- Shapes verified in tests: `official-page-monitor-state-v1` (last-good hashes, bounded normalized segments, validators, timestamps) and `official-page-change-report-v1` (`first_seen`, hashes, `content_changed`/`text_changed`, full counts, capped excerpts, fixed failure category).
- Honest limits: normalization is not semantic diffing; dynamic regions can create noise; no live PAC URL was verified; success is not legal currency, validity, coverage, or answer-quality evidence.
- Validator repair (2026-11-07): a missing or empty `Content-Type` header now fails closed as `unsupported content type` instead of inheriting the email `text/plain` default (scenario 4); `./scripts/init.sh --feature official_page_change_monitor` — focused tier passed (`50 passed`).

## Validator checklist

- [ ] Scope matches the contract; non-goals respected.
- [ ] Config accepts only the three issuers, their first-party approved hosts, HTTPS URLs on the default port with no credentials/fragment/root path, unique ids, and unique URLs.
- [ ] Fetch enforces the 15-second timeout, 5 MiB cap, same-host HTTPS redirects, supported content types, and `200`/`304` semantics, and the focused suite proves no live network fetch.
- [ ] HTML/plain-text extraction skips scripts/styles, normalizes deterministically, and fails closed on empty text or text bounds.
- [ ] Diff reports only `added`/`removed`/`changed` text with full counts and capped excerpts; markup-only changes are distinguished from text changes.
- [ ] State keeps the last-good snapshot across failures, validates its shape and all output paths before any request, and handles `304` only with a prior snapshot.
- [ ] Report and state are deterministic under a fixed `--now`, ordered by id, atomic, and refused under `knowledge/` or when equal.
- [ ] The single CLI prints plain-language `Result:` lines and exits `0`/`1`/`2` as specified; no page text or hidden claim leaks to stdout.
- [ ] No canonical catalog/passages/releases/indexes, `/ask`, retrieval, discovery, ingestion, or scheduler behavior changed; no owner-guide step added.
- [ ] Focused verification runs unchanged through `./scripts/init.sh --feature official_page_change_monitor`; evidence and honest limits are recorded.
- [ ] `docs/validations/official_page_change_monitor.md` is created by the independent validator; acceptance is validator-only with no owner walkthrough.
