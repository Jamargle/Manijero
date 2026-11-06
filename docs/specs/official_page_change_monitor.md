# Feature Spec: `official_page_change_monitor`

## Source metadata

- `id`: official_page_change_monitor · `area`: knowledge · `depends_on`: `official_source_monitoring` · `status` at planning: `not_started`
- User-visible behavior: none in the app. A developer runs `backend/scripts/monitor_official_pages.py`, which reports added, removed, or changed visible text on explicitly configured FEGA, MAPA, and Junta PAC pages.
- Verification: one offline pytest module covering normalization, diff classification, bounds, state/report isolation, determinism, and the command's plain-language result lines; commands in [Focused verification](#focused-verification-required).
- Notes: developer-only with validator acceptance only; no owner walkthrough. The full owner decision is in [Notes](#notes).

## Notes

- Owner decision (2026-11-06), verbatim intent: Standalone offline-in-tests backend command that compares approved FEGA, MAPA, and Junta PAC page snapshots by content hash and a bounded normalized text diff; writes a deterministic change report and monitoring state outside `knowledge/`. It never fetches in tests, never changes canonical catalog/passages/releases/indexes or `/ask`, and never claims legal currency. Detect added/removed/changed text only, never interpret legal meaning. One named command with plain-language `Result:` lines; no scheduling, alert delivery, or browser/JS execution; respect the existing approved-host allowlist and response bounds. Developer-only: no owner-guide step. Acceptance: validator accept is final, no owner walkthrough.
- The command is a review signal only. It does not create discovery candidates, fetch linked documents, classify relevance, parse legal signals, or write any knowledge artifact. State keeps only the bounded normalized text needed for the next diff; it is operator data outside `knowledge/` and is never answerable or committed.
- `feature_list.json` status stays owned by the selector; this planner does not change it.

## Goal

Give a developer a bounded, repeatable way to notice that an approved official PAC page changed, with evidence a person can review. The command compares a page's exact response bytes and its normalized visible text against the last successful snapshot; it reports only added, removed, or changed text and never says what a change means.

## Non-goals

- No scheduling, recurring dispatch, retry loop, alert delivery, dashboard, or scheduler integration.
- No browser, JavaScript, headless renderer, OCR, PDF parsing, or linked-resource fetching; only the configured page response is read.
- No legal interpretation, validity or currency decision, relevance classification, candidate creation, ingestion, or corpus/release/index change.
- No change to `/ask`, retrieval, generation, abstention, canonical `knowledge/` artifacts, knowledge schemas, or the client.
- No new issuer or host; no claim that a configured URL is a PAC page or that coverage is complete.
- No owner-guide step and no owner walkthrough.

## Job story

When an official FEGA, MAPA, or Junta PAC page may have changed, I want one local command to show whether its bytes and visible text changed and what text was added, removed, or changed, so I can decide whether a person should review the page without the assistant silently ingesting or interpreting it.

## Acceptance scenarios

### 1. First run records a baseline

Given a valid config whose page host is approved for its issuer, when the command runs and the page returns a supported response, then state records the URL, issuer, retrieval time, HTTP status, exact-byte SHA-256, normalized-text SHA-256, validators when supplied, and the bounded normalized text segments; the report records the page identity, hashes, and `first_seen`; the page is not reported `changed`.

### 2. Identical repeat is unchanged

Given a prior successful snapshot, when the same page returns the same bytes and the same normalized text, then the report says `unchanged`, records no added/removed/changed text, and replaces the snapshot only with equivalent values.

### 3. Changed page reports only text deltas

Given a prior snapshot, when the page's normalized visible text changes, then the report lists bounded excerpts for `added`, `removed`, and `changed` segments with full counts, caps excerpts per page and per excerpt, and reports `changed` with `text_changed: true`. A change only in markup, script, style, or whitespace that normalization removes reports `content_changed: true`, `text_changed: false`, and zero text deltas. No excerpt is interpreted.

### 4. Unsafe destination or unsupported response fails closed

Given a URL that is not HTTPS, uses a non-default port, has credentials or a fragment, has a root or empty path, uses a host outside the issuer's first-party approved hosts, or redirects to another host or scheme; or a response that times out, exceeds the byte cap, is not `text/html`/`application/xhtml+xml`/`text/plain`, exceeds the text bounds, or returns an unsupported status, when the command runs, then that page is reported `failed` with a fixed, value-free category, no snapshot is overwritten, and the other pages still produce their own outcomes.

### 5. Failure preserves last-good evidence

Given a prior successful snapshot, when a later fetch fails, then state retains the prior content hash, text hash, normalized segments, validators, and last-success time; the report says `failed`; the command exits `1` when any page failed; and a later successful fetch diffs against the retained last-good snapshot.

### 6. Conditional request and unreadable baseline

Given ETag or Last-Modified was recorded, when a later request receives `304`, then the prior snapshot is retained and the page reports `unchanged`; a `304` without a prior successful snapshot is a failure. Given a successful response with no readable visible text, the result is a failure, not an empty baseline.

### 7. Deterministic, isolated output

Given the same config, page bytes, prior state, and injected `--now`, when the command runs twice, then the report bytes are identical and ordered by page id. State and report are refused under `knowledge/`; raw bytes, HTML, and script are never stored; canonical catalog, passages, releases, indexes, `/ask`, and retrieval behavior remain unchanged. The report has no currency, validity, legal-effect, or recommendation field, and the command prints no such claim.

## Technical approach

- Add one stdlib-only module `backend/app/page_monitor.py` and one thin CLI `backend/scripts/monitor_official_pages.py`. The module imports only the standard library and `source_catalog` for the host policy; it does not import the answer service, retrieval, release, discovery, or ingestion modules. The module owns `main(argv=None, now=None)`, config/state/report logic, and exit codes; the script only calls it. That script is the one named command; no new `./scripts/init.sh` mode is added because the feature is developer-only and the existing `--feature` tier verifies it. No new dependency or scheduling.
- Config is a JSON object with exactly one key, a non-empty `sources` array; each source has exactly `id`, `issuer`, and `url`. `id` is unique and matches `^[a-z0-9]+(?:[-_][a-z0-9]+)*$`; duplicate ids or URLs are rejected. `issuer` is exactly `FEGA`, `MAPA`, or `Junta de Andalucía`.
- Page hosts are the first-party pair already in `backend/app/source_catalog.py::ISSUER_ALLOWED_HOSTS` for each of those issuers: `fega.gob.es`/`www.fega.gob.es`, `mapa.gob.es`/`www.mapa.gob.es`, and `juntadeandalucia.es`/`www.juntadeandalucia.es`. Add no host; a test asserts this set is contained in `APPROVED_HOSTS`. Require HTTPS on the default port, no credentials, no fragment, and a non-root path.
- Fetch with `urllib` GET under a 15-second timeout, a 5 MiB response cap, the existing same-host HTTPS redirect rule, and `If-None-Match`/`If-Modified-Since` when recorded. Accept HTTP `200` and handled `304`; for `200`, accept only `text/html`, `application/xhtml+xml`, or `text/plain`. Never follow links, load subresources, or execute scripts. Tests inject a fake request seam; no test opens a socket.
- Extract visible text with stdlib `html.parser.HTMLParser` for HTML/XHTML, or normalize plain-text lines as-is. Skip `script`, `style`, `noscript`, `template`, and comments; emit blocks on block-level boundaries; decode with the declared charset, then UTF-8, then `cp1252` as the ingestion code does.
- Normalize deterministically: Unicode `NFKC`, collapse all whitespace runs to one space, strip, and drop empty blocks. Fail closed if no readable text remains, if segments exceed 5,000, or if characters exceed 2,000,000. Hash the exact response bytes and the normalized text joined by `\n`.
- Diff only normalized segment lists with `difflib.SequenceMatcher(autojunk=False)`: inserts become `added`, deletes become `removed`, and a `replace` block pairs segments in order up to the shorter length as `changed`, with any remainder as `added` or `removed`. Report full counts and at most 50 excerpts of at most 240 characters each; excerpts carry before/after text only for `changed`. No semantic matching, filtering, or interpretation.
- Persist `official-page-monitor-state-v1` (one record per id, last-good hashes/segments/validators/timestamps) and write `official-page-change-report-v1` (sorted by id). Both are JSON with `sort_keys`, written atomically, refused under `knowledge/`, refused when equal, and never written before validation; validate config, state shape, and output paths before any request, and the command writes no other file. Write the report first, then state; a state write failure exits `2` and the next run still sees the change against the old state.
- The CLI is the only entry point: `--config`, `--state`, `--report`, and optional `--now` (ISO-8601; an invalid value is a `2`) for deterministic replay. It prints plain-language lines such as `Result: fega-pac: 2 added, 1 changed, 0 removed.`, `Result: mapa-pac: no change.`, and `Result: junta-pac: could not be checked (upstream request failed).`, then a summary such as `Result: 3 pages checked: 1 changed, 1 unchanged, 1 failed. Report: <path>.`, with no page excerpts or hidden text. Exit `0` when every page was checked (first seen, unchanged, or changed), `1` when any page failed, `2` for config, state, path, or write errors.
- Never log or store arbitrary upstream exception text, response bodies, raw HTML, or JavaScript. Use this closed failure set: `upstream request failed`, `upstream returned HTTP <code>`, `unsupported content type`, `response exceeded size limit`, `page text exceeded limit`, `page had no readable text`, `redirect rejected: host or scheme changed`, and `received 304 without a prior successful snapshot`. The command is not wired into `/ask`, retrieval, release building, discovery, ingestion, or the scheduler.

## Expected file changes

- `backend/app/page_monitor.py` — create; config/host validation, bounded fetch, text normalization, diff, state/report, and command runner.
- `backend/scripts/monitor_official_pages.py` — create; thin `main()` wrapper for the single named command.
- `backend/tests/test_page_monitor.py` — create; offline tests for hosts, bounds, normalization, diffs, last-good state, determinism, path isolation, and `Result:`/exit behavior.
- `backend/tests/fixtures/page_monitor/` — create; small synthetic baseline, changed, markup-only, empty-text, and oversized fixtures.
- `backend/README.md` — update; add a short "Manual official-page change monitoring" section (~30 lines) with config shape, command, report/state paths, exit codes, and limits.
- `ARCHITECTURE.md` — update; add the page-monitor runtime boundary next to the existing source monitor.
- `docs/constraints/answers-and-knowledge.md` — update; add the durable review-only/outside-`knowledge/` rule.
- `docs/validations/official_page_change_monitor.md` — created by the independent validator only.
- `knowledge/`, `contracts/`, `shared/`, client code, `docs/owner-guide.md`, `scripts/init.sh` — no changes; the focused tier uses the existing `--backend-tests`/`--feature` runner.

## Visual design impact

No UI involved. No `DESIGN.md` section applies.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — a new operator-side backend module and CLI boundary must be visible beside `source_monitor.py` and `change_impact.py`.
- `docs/constraints/answers-and-knowledge.md`: update — page changes are review signals; state/report stay outside `knowledge/`; no canonical, release, index, or `/ask` effect; no legal-currency claim.
- `AGENTS.md`: not needed — no workflow, startup path, or repo-wide rule changes; developers use the existing `--backend-tests` and `--feature` tiers.
- `backend/README.md`: update — developer command, config/state/report shape, exit codes, and honest limits.
- `docs/owner-guide.md`: not needed — developer-only feature; no owner operation or walkthrough.
- `docs/risks-and-open-questions.md`: update only if evidence shows a new operational risk; the normalized-diff and dynamic-page limits otherwise stay in this appendix.

## Focused verification (required)

<!-- verify:start -->
```sh
./scripts/init.sh --backend-tests tests/test_page_monitor.py -q
```
<!-- verify:end -->

## Appendix

See [`official_page_change_monitor.appendix.md`](official_page_change_monitor.appendix.md) for repository research, ordered tasks, the verification plan, evidence, and the validator checklist.
