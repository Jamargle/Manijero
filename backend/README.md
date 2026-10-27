# Manijero backend

The local FastAPI service exposes `GET /health` and a source-grounded `POST /ask`.
From the repository root, start it with the shared startup script:

```sh
./scripts/init.sh --backend
```

The script creates `backend/.venv` when needed, installs/updates the runtime
requirements, sets `MANIJERO_ACTIVE_CAMPAIGN=2026` unless already configured,
and launches Uvicorn with reload enabled, bound to `0.0.0.0` so the Android
emulator can reach the host through `10.0.2.2`. This also makes the development
server reachable from your local network; use a trusted network/firewall, or set
`MANIJERO_BACKEND_HOST=127.0.0.1` to restrict it to this computer (Desktop will
still work, but Android will not). Stop it with `Ctrl+C`. To start it manually
instead, run:

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
MANIJERO_ACTIVE_CAMPAIGN=2026 python -m uvicorn app.main:app --reload --host 0.0.0.0
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question":"¿Qué información hay?","land_context":{"mode":"general","lands":[]}}'
```

For a physical Android device on the same trusted LAN, use the computer's LAN
address as the Android endpoint when building, for example
`./gradlew :androidApp:assembleDebug -PmanijeroAskBaseUrl=http://192.168.1.20:8000`.
The emulator default remains `http://10.0.2.2:8000`.

For backend tests and artifact validation, install the development dependencies
in a virtual environment instead:

```sh
python -m pip install -r requirements-dev.txt
```

The runtime requirements intentionally do not include `pytest` or `jsonschema`;
the latter is used by the focused PAC answer-evaluation test tier to validate
Draft 2020-12 schemas and artifacts.

Successful response:

```json
{"status":"ok","service":"manijero-backend"}
```

`/health` reports only that this process is serving HTTP requests. It does not
check corpus readiness. `/ask` reads the local `knowledge/source_catalog.json`
and `knowledge/passages.json` artifacts and uses the accepted retrieval,
grounding, abstention, and land-clarification decisions. It does not call a
hosted model or the network. Every `/ask` request requires `MANIJERO_ACTIVE_CAMPAIGN`
to be explicitly set to a four-digit year (for example `2026`); it is never inferred
from today's date or the question. Campaign-neutral and matching campaign sources
may be used. Rotate expired campaign sources and their passages out of the active
artifacts in a reviewed update.

The canonical catalog contains four independently reviewed official sources
and four approved literal passages. `/ask` supports only the three topics in
[`knowledge/pac_coverage.md`](../knowledge/pac_coverage.md) and safely abstains
when it cannot assemble a grounded answer. Fixture-backed answers in tests are
synthetic and do not establish legal coverage. Invalid or unreadable corpus files and
missing/invalid campaign configuration or unsafe corpus data returns a generic `503`; malformed JSON returns `400`,
and valid JSON that violates the request contract returns `422`. Error responses
do not echo question, land, file, or corpus values.

## Offline retrieval baseline

`app/retrieval.py` is the offline retrieval boundary over reviewed passages of
approved catalog sources. It is standard-library only, never performs network
access, re-validates the catalog with `app/source_catalog.py`, and refuses to
index when that catalog is invalid. The `/ask` route composes it with the
accepted grounded-answer pipeline; no LLM call is configured.

Run the report-only baseline against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints per-question expected-passage ranks plus `hit@k`, `recall@k`, and MRR
(`--json` for machine-readable output). Thresholds are **not** enforced: the
numbers come from a small synthetic fixture corpus, not from real user questions
or legal documents. See `knowledge/README.md` for the passage-set contract and
the eligibility rules.

## Offline grounded answer generation

`app/generation.py` turns retrieval candidates into a plain-Spanish answer whose
material claims are each traceable to a reviewed passage. It imports `Retriever`
and `RetrievedPassage` from `app/retrieval.py`, which stay the only evidence
source: generation never re-reads the catalog or the passage set and never
re-implements eligibility.

It is standard-library only, offline, and configured with **no model provider**.
The default and only enabled generator is the code-composed extractive one; a
draft is re-checked by `verify_draft` before assembly, so a citation marker that
resolves to nothing, an uncited sentence, a figure or date absent from the cited
passage, a non-literal `critical` claim, or an eligibility assertion
(`tienes derecho a`) rejects the whole draft. The extractive generator writes
each claim on its own line before verification, and a line break is a claim
boundary, so an excerpt without terminal punctuation cannot merge with the next
candidate's claim and inherit its figure or critical-literal rules. The pipeline
then returns a `NotAnswered` reason code and no text; `safe_abstention` owns the
user-facing limitation and next step.

Run the report-only grounded-generation tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, the produced answer, every material claim
with its cited candidate numbers, and the per-claim grounding verdict
(`--json` for machine-readable output). Grounding invariants are **enforced**
(exit `1`); answer coverage is not, unless `--fail-on-miss` is passed. `/health`
remains liveness-only, and no model provider is configured.

## Offline abstention decisions

`app/abstention.py` turns every "no safe answer" outcome into one deterministic,
offline, code-owned abstention. It is standard-library only, imports
`app/generation.py` and `app/retrieval.py` unchanged, and never reads a catalog
or a passage file itself, never calls a model or the network, and never emits a
draft sentence, candidate excerpt, source, figure, or date.

The taxonomy is stable and machine-readable. Pre-checks (run before the
generator) and pipeline mappings produce exactly one reason:

| Reason | Trigger |
|---|---|
| `invalid_question` | Blank question, or longer than the accepted 2,000-character bound. |
| `no_evidence` | Retrieval returned no candidate (generation `no_candidates`). |
| `insufficient_evidence` | Candidates existed but no verifiable claim could be assembled (generation `grounding_failed`). |
| `stale_evidence` | The corpus declares sources but none is eligible as of `--as-of` (expired, non-`approved`, or non-`current`). |
| `conflicting_evidence` | Two `critical` candidates in the citation window state different values for the same documented unit. |
| `false_premise` | The question presupposes an instrument/article reference that no retrieved candidate contains. |
| `unsafe_request` | A generated claim asserts the person's legal status (generation `policy_failed`). |
| `generator_abstained` | The generator explicitly declined; its copy is discarded. |
| `generation_error` | The generator raised or returned an unusable object. |

Server-side copy is **code-owned**: `ABSTENTION_MESSAGES` maps every reason to one
pinned plain-Spanish message, an `Abstention` has no text field, and no message
contains a digit or a date, so an abstention can never invent a deadline or an
amount. `to_abstention_response` emits exactly the accepted `AskResponse` keys
with `status: "abstained"`, `sources: []`, and `land_ids_to_choose: []`. Because
`AskResponse` rejects extra properties, the sub-reason stays a Python-level value
and `contracts/` is untouched. Detection is lexical and conservative (a retrieval
miss or two unrelated critical passages sharing a unit can abstain); that is the
safe direction, and the measured trap set and any score threshold belong to
`land_safety_evaluation`.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_abstention.py \
  --catalog backend/tests/fixtures/abstention/catalog.json \
  --passages backend/tests/fixtures/abstention/passages.json \
  --eval backend/tests/fixtures/abstention/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, reason, generation reason, issue codes, and
emitted message (`--json` for machine-readable output), and reports whether the
corpus is `current` or `not_current`. Abstention invariants (no sources, no land
choices, a non-blank message at most 1,200 characters with no digit or date, and
a reason inside the taxonomy) are **enforced** (exit `1`); outcome coverage is not
unless `--fail-on-miss` is passed. A catalog whose sources are all ineligible as
of `--as-of` abstains as `stale_evidence` for every question; a malformed passage
set, an unknown `source_id`, or an unreadable file stays a hard error (exit `2`).
`/health` remains liveness-only, and no model provider is configured.

## Offline land clarification decisions

`app/clarification.py` makes the accepted `needs_land_clarification` response actually happen. It
composes the accepted modules unchanged (`app/retrieval.py`, `app/abstention.py`,
`app/generation.py`): it never reads a catalog or a passage file itself, never calls a model or the
network, and never filters by applicability anywhere else.

When the question depends on a detail the supplied lands differ on, the person is asked which land
(or lands) the question is about instead of the service guessing one arbitrarily. Only the opaque
local ids are returned on the wire; the client owns the names and collects the selection, so no
name, note, area, or timestamp leaves the device.

- A clarification is offered **only** for `mode: all_active` with **two or more** lands. `general`,
  a single land, and a `selected` request (the person has already chosen) delegate to the accepted
  `answer_or_abstain`, so a `selected` request is never asked to clarify again.
- The only discriminating dimensions are `water_regime` and `production_method` (the two a request
  can carry); `crop` is not a request field, so a `crop` restriction applies to every land and never
  discriminates. Detection is conservative and lexical, in the citation window (the first `max_claims`
  candidates, matching `abstention`).
- An omitted, blank, or `unknown` land attribute is compatible with every candidate and never
  excludes one; only a known value that disagrees with a candidate's declared applicability excludes
  that candidate, and no value is ever inferred.
- A clarification payload is exactly the accepted `AskResponse` keys with
  `status: "needs_land_clarification"`, `answer: ""`, `sources: []`, `land_scope: "selected"`, and a
  non-empty, unique list of the request's own land ids. `contracts/` is untouched.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_clarification.py \
  --catalog backend/tests/fixtures/clarification/catalog.json \
  --passages backend/tests/fixtures/clarification/passages.json \
  --eval backend/tests/fixtures/clarification/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, the chosen land ids for a clarification, and the per-outcome
counts (`--json` for machine-readable output). Clarification invariants (empty answer, no sources, a
non-empty list drawn from the request's own land ids) are **enforced** (exit `1`); outcome coverage is
not unless `--fail-on-miss` is passed. A malformed passage set, an unknown `source_id`, or an
unreadable file stays a hard error (exit `2`). `/health` remains liveness-only, and no model
provider is configured.

## Offline land-safety evaluation

`app/land_safety_eval.py` is the offline, report-only safety harness. It runs the
accepted end-to-end decision (`app/clarification.py::answer_with_clarification`,
which already composes retrieval, grounding, abstention, and land clarification)
over a reviewed, source-anchored case set and reports, per category, whether the
service returned the correct sources, abstained safely, or clarified the correct
land. It imports the accepted modules unchanged: it never re-implements
eligibility, grounding, or clarification, never reads a catalog or a passage file
itself, never configures a model provider, and never touches the network. Grading
is deterministic rule checking, not a semantic judge.

A case is a Git-tracked, human-reviewed artifact. A case whose expectation turns
on a critical fact must carry a completed `review` block; without it the set fails
closed at load time (exit `2`). The harness records that provenance but a human
must verify the fact itself. The case-set contract is `knowledge/land_safety_eval.schema.json`
(`land-safety-eval-v1`); see `knowledge/README.md` for the fields and the review
procedure.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_land_safety.py \
  --catalog backend/tests/fixtures/land_safety/catalog.json \
  --passages backend/tests/fixtures/land_safety/passages.json \
  --cases backend/tests/fixtures/land_safety/cases.json \
  --as-of 2026-10-13 --k 5
```

It prints each case's outcome and per-check verdicts, the per-category table, the
metric block, and the critical-review section (`--json` for machine-readable
output). The enforced **safety invariants** (a payload that leaks or invents:
an abstention carrying a source, a figure, or a date; a clarification carrying an
answer or a foreign land id; an answered payload with no source or an
out-of-range marker) make it exit `1`. Coverage metrics are **report-only**: an
expected-source/clarification mismatch only exits `1` with `--fail-on-miss`, and
`--passages`/`--cases` may be omitted for a corpus summary that invents nothing.
`/health` remains liveness-only, and no model provider is configured.

The measured fixture baseline is: `covered_source_hit_rate` `1.000 (2/2)`,
`correct_abstention_rate` `1.000 (2/2)`, `correct_clarification_rate`
`1.000 (1/1)`, `no_over_clarification_rate` `1.000 (3/3)`, and
`expected_outcome_match_rate` `1.000 (6/6)`. It is **synthetic and
implementer-authored**: it exercises the mechanism and the trap taxonomy, not
legal coverage or real user questions, and it is not legal-coverage evidence.
The `MasterPlanV3` §9.2 numbers (`hit@5 85%`, correct abstention `100%`, invented
numbers/dates `0`) are **inherited proposals, not enforced release gates**;
enforcement is a later, separately agreed change.

## Offline PAC answer evaluation

`app/answer_eval.py` validates the `pac-answer-eval-v2`
`knowledge/pac_answer_eval.json` artifact and calculates a deterministic,
report-only evaluation of its cases through the local `/ask` route. The artifact
declares its reviewed coverage areas (3 topics and 5 boundaries), the out-of-scope
omissions, and an `author_only` review role on every case. The report includes
assertion denominators (`answered_cases`, `abstention_cases`,
`clarification_cases`), per-area counts, author-review metadata, the omissions,
and per-case missing expected source/passage IDs or critical facts. Run it with
the pinned inputs:

```sh
backend/.venv/bin/python backend/scripts/evaluate_pac_answers.py \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --active-campaign 2026 --as-of 2026-10-26 --k 5
```

All 14 cases are synthetic, source-anchored, and reviewed only by the project
author (recorded as `author_only`); this is **not** independent legal review and
does not establish answer quality or coverage beyond the listed cases. The
current result is 13/14 expected states, 11/11 expected-answer cases answered,
8/11 answering cases with the expected source and passage, 9/11 with the expected
critical literal, and 2/3 expected abstentions. The report keeps known gaps
visible: `canal-sga-2026`, `fecha-modificacion-2026`, and
`distingue-fechas-2026` cite a different reviewed passage, and
`reclamacion-fuera-de-alcance` answers an out-of-scope reclamación with the
modification deadline. The exact matrix and case-level limits are in
`knowledge/pac_coverage.md`.

Citation matching uses exactly the catalog and passages supplied to the command.
Repeat identical inputs for byte-identical output. Integrity/input/runtime errors
exit nonzero; outcome mismatches and coverage metrics do not. There is no numeric
quality threshold.

Tests:

```sh
cd backend && python -m pytest
```

## Manual official-source monitoring

`app/source_monitor.py` polls only explicitly configured HTTPS endpoints on the
exact approved official-host allowlist. It supports RSS/Atom XML and JSON
responses, including the BOJA RSS and BOE Open Data API endpoints; it does not
interpret response contents or fetch linked documents. A successful snapshot
stores retrieval time, URL, HTTP status, ETag/Last-Modified when supplied, and
SHA-256 of the exact response bytes. A changed feed is a review candidate only;
the scanner never writes `knowledge/source_catalog.json` or `knowledge/passages.json`.

Create an owner-reviewed configuration file, for example:

```json
{"sources":[
  {"id":"boe-api","url":"https://www.boe.es/datosabiertos/api/api.php","format":"json"},
  {"id":"boja-rss","url":"https://www.juntadeandalucia.es/boja/distribucion/s51.xml","format":"rss"}
]}
```

Dispatch manually (or call this command from an owner-managed scheduler):

```sh
cd backend
python scripts/scan_official_sources.py --config source-monitor.json --state var/source-monitor-state.json
```

Exit `0` means each configured endpoint succeeded; `1` means at least one
endpoint failed (the JSON report includes actionable failure categories and
retains its last good hash/time); `2` means config/state could not be read or
validated. Use a durable, access-controlled local state path and back it up if
operational history matters. Conditional requests are sent when validators are
available. Requests have a 15-second timeout and 5 MiB response cap; redirects
are allowed only to the same HTTPS host. There is no in-process recurring
scheduler, retry loop, document ingestion, legal-change interpretation, or
automatic canonical update. Successful polling is not evidence of legal
coverage or corpus currency.

## Manual official-publication discovery

`app/source_discovery.py` scans configured registries into a separate pending
queue; it does not fetch publication bodies or modify the canonical catalog or
passages. BOE uses the documented daily sumario XML API; BOJA uses its
officially documented calendar endpoint to enumerate bulletin numbers, then
fetches each issue through the bulletin endpoint. The scan is bounded to 400
issues and 160 MiB aggregate BOJA response bytes (5 MiB per request); exceeding
a bound fails the registry scan without committing partial candidates.
FEGA/MAPA first-party registries are not
verified and are reported unchecked, not treated as empty. The registry host
`datos.juntadeandalucia.es` is exact-configured for the API only; candidate
publication URLs still require exact issuer-host approval.

Copy `knowledge/official-discovery-config.example.json`, adjust BOE date and
BOJA year, then run:

```sh
python3 backend/scripts/discover_official_sources.py \
  --config /path/to/discovery-config.json \
  --state /path/to/official-discovery-state.json
```

Exit `0` means every attempted supported registry succeeded, `1` means an
attempt failed, and `2` means invalid config/state. The report still lists
unconfigured registries and FEGA/MAPA as unchecked; exit `0` is not full
coverage. Each request has a 15-second
timeout and 5 MiB response cap; HTTPS redirects remain on the exact same host.
Only candidate metadata and observation hashes/times are retained, not response
content. Repeated records add no duplicate observation; changed title/URL
versions retain prior observations. Failures preserve candidates and
last-success timestamps. Candidates remain `pending`; a human must verify
provenance and approve any canonical change. See
`knowledge/official-discovery-state.schema.json`.

## Manual official-document candidate ingestion

`app/document_ingestion.py` fetches the pending publication candidates produced
by discovery into a local **quarantine**. It is the only command in this
repository that downloads a publication body, and it is still not an
answerability path: it never reads or writes `knowledge/source_catalog.json`,
`knowledge/passages.json`, or any index, and every ingested record stays
`review_status: pending`. A human must review, extract approved passages, and
merge a canonical change separately.

**Admission rules.** A candidate is fetched only when its declared issuer is one
of the approved catalog issuers and its `publication_url` uses HTTPS on that
issuer's exact approved host, including the approved `www.` alias where listed
(no subdomain or suffix matching), with no credentials, non-443 port, site root,
or fragment. Anything else is rejected before a request is made. Redirects are
followed only when every hop stays on HTTPS and on an exact host approved for
the same issuer, at most three hops; any other redirect, a final URL outside
that host set, or a non-200 response fails the candidate. FEGA and MAPA
publications still need a BOE host unless the URL host is one of their own
approved hosts.

**Inputs.** `--discovery-state` is the `official-discovery-state-v1` file.
`--monitor-state` is optional. Monitoring deliberately retains only feed
response metadata, not linked document URLs, so it contributes **zero**
candidates and each monitored source is reported as
`unchecked / no_document_candidates`; the command does not guess documents from
a feed.

Run it from the repository root with an operator-owned state and quarantine
path outside `knowledge/`:

```sh
backend/.venv/bin/python backend/scripts/ingest_official_documents.py \
  --discovery-state /path/to/official-discovery-state.json \
  --monitor-state /path/to/source-monitor-state.json \
  --state /path/to/official-ingestion-state.json \
  --quarantine /path/to/official-document-quarantine
```

Omit `--monitor-state` when no monitoring state exists. The JSON report lists
one outcome per candidate (`extracted`, `unchanged`, `failed`, `rejected`) with
fixed failure categories and the preserved provenance hashes. Exit `0` means no
candidate failed or was rejected, `1` means at least one did (the run still
persists every other outcome), and `2` means the run aborted before producing a
report: an unreadable or invalid config/state file, a discovery state over 1,000
candidates, a state/quarantine path inside the repository `knowledge/`
directory, or an unexpected exception. Those pre-fetch rejections make no
request. Exit `0` is not coverage evidence: the report still shows the
monitoring gap and any rejected candidate.

**Bounds.** One candidate is requested once per run with no retry loop. Each
request has a 15-second timeout, a 10 MiB response cap, and at most three
same-issuer redirects; exceeding any of these fails that candidate. Per-candidate
PDF/text bounds are 20 MiB decompressed, 500 pages, 20,000 objects, 200 fonts per
page, 65,536 CMap entries, and 5,000 blocks / 2,000,000 characters; exceeding one
fails that candidate closed. A discovery state containing more than 1,000
candidates aborts the whole run as exit `2` before any fetch. Only
`application/pdf`, `text/html`, and `application/xhtml+xml` declared types are
accepted, and the body must have the matching PDF/HTML signature.

**What is preserved.** For each accepted candidate the quarantine directory
`<quarantine>/<candidate_id>/` holds the exact original bytes
(`original-<sha256>.<pdf|html>`) and the extracted structure
(`extracted-<sha256>.json`), named by content hash so a changed version does
not overwrite the prior copy. The state records the discovery provenance
(issuer, registry URL, publication URL, stable identity, observation version
hash), retrieval time, declared/content type, byte size, original SHA-256,
extractor version, extracted-text SHA-256, page/block counts, previous original
hash, and a bounded attempt history. HTML blocks carry a heading path as their
`section`; PDF blocks carry `Página N`. The readable contracts are
`knowledge/official-ingestion-state.schema.json` and
`knowledge/official-ingestion-document.schema.json`.

**Failure and recovery.** A failed or rejected attempt leaves any previous good
extraction and its files untouched, records the fixed failure category, and
keeps the last-success time. Re-running the same discovery state retries failed
candidates and skips an unchanged successfully ingested candidate (same version
hash, current extractor version/media type, and files present). A changed
discovery version hash re-fetches
and re-extracts, preserving the old hashed files and recording
`previous_original_sha256`. Duplicate candidate URLs and duplicate document
bytes inside one run are rejected (`duplicate_candidate`, `duplicate_content`)
rather than ingested twice. If the ingestion state file is invalid, the command
exits `2` and overwrites nothing. To start over, stop the command, move the
state file and quarantine directory aside, and run again; the deleted quarantine
is not recoverable from the service.

**Refreshing extraction.** A stored `extractor` value that differs from the
current `manijero-document-extractor-v1` makes the candidate eligible for a
re-fetch and re-extraction on the next run. Original bytes stay hashed per
version and are not deleted, but when the bytes are unchanged the same-named
`extracted-<sha256>.json` is replaced by the new extraction, so keep your own
copy if you need to compare parser outputs. Because discovery's `version_hash`
covers only title and URL, a publisher replacing bytes at the same stable URL
without changing either is not detected as a new version. To force a refetch,
remove that candidate's state record (or use a fresh state file) and keep the
old quarantine files for comparison.

**Operational limits.** `page_count` counts PDF pages that produced at least one
text block, not the PDF's declared page count. The quarantine grows with every
changed version and is never garbage-collected. The command has no lock: run one
ingestion process per state/quarantine pair at a time. The state is validated
structurally and file-presence paths must stay inside the candidate's quarantine
directory, but the remaining provenance values in the state file are trusted
operator input.

**Extraction limits.** PDF extraction is standard-library and handles
uncompressed or Flate-compressed content streams with literal/hex strings,
UTF-16BE/LE string BOMs, PDF 1.5 object streams, multiple page content streams,
and embedded-font `ToUnicode` CMaps (`bfchar`/`bfrange`, including array
ranges). It does **not** decode LZW/ASCII85/encrypted PDFs, scanned images, or
glyphs missing from an incomplete subset-font map. Such documents fail as
`unsupported_pdf_encoding`, `malformed_document`, or `no_extractable_text`, or
leave `U+FFFD` placeholders where a map omits a used code; blocks containing
only replacement characters are dropped. OCR is not implemented or measured.

Live smoke checks on 2026-10-27 fetched and parsed one BOE PDF (2 pages, 4,179
characters, no replacement characters) and one BOJA PDF whose HTTP `307`
redirect stayed on the same issuer (35 pages, 80,388 characters, about 6.3%
replacement characters because subset fonts omitted glyph mappings). That is
not a general accuracy measurement: a reviewer must still compare the original
and extracted text, especially for BOJA subset fonts, before proposing a
canonical update. HTML parsing skips
`script`/`style`/`template`/`noscript` and preserves heading hierarchy, but it
is not a full-text browser rendering.

The fetch uses the platform CA trust store. If `urllib` raises
`CERTIFICATE_VERIFY_FAILED` while `curl` succeeds, set `SSL_CERT_FILE` to a CA
bundle (for example the `certifi` bundle inside `backend/.venv`) rather than
disabling certificate verification.

The extractor and state never log document text or upstream exception text;
failure categories are fixed strings. Keep the quarantine and state directories
access-controlled and back them up if review history matters.

## Legal change-impact analysis

`app/change_impact.py` compares the versions that candidate ingestion recorded
and links possible impact to the approved catalog, reviewed passages, and
reviewed answer-evaluation cases. It is read-only: it never reads or writes an
answer path, never edits `knowledge/source_catalog.json`,
`knowledge/passages.json`, or `knowledge/pac_answer_eval.json`, never changes a
lifecycle or review status, and never retires, replaces, or approves a source.
Every candidate that could touch reviewed knowledge stays for an identified
human reviewer.

**Inputs.** `--ingestion-state` and `--quarantine` are the
`official-ingestion-state-v1` file and quarantine directory written by
`ingest_official_documents.py`; only candidates whose state is `extracted` have
text to analyze. `--catalog` and `--passages` are the approved
`source-catalog-v1` and `passage-set-v1` artifacts, validated again with the
existing validators as of `--as-of`; an invalid catalog or passage set is a
hard error. `--cases` is optional and reads the identity and reference fields of
a `pac-answer-eval-v1` case set (`app/answer_eval.py` remains the authoritative
validator for the full case contract). `--as-of` is required and is the only
date in the report.

Run it from the repository root with the ingestion state and quarantine produced
by the previous step:

```sh
backend/.venv/bin/python backend/scripts/analyze_legal_changes.py \
  --ingestion-state /path/to/official-ingestion-state.json \
  --quarantine /path/to/official-document-quarantine \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json \
  --as-of 2026-10-27 \
  --report /path/to/legal-change-impact-report.json
```

Omit `--cases` when no reviewed case set is available. The command writes the
report and prints a compact summary (counts plus the ids that need review).
Exit `0` means no candidate needs review and no analysis failed, `1` means the
report was written and at least one candidate needs review or failed analysis,
and `2` means the run aborted before writing: an unreadable or invalid catalog,
passage set, case set, or ingestion state, a missing `--as-of`, more than 1,000
candidates, a report path inside the repository `knowledge/` directory, or an
unexpected exception. Error output is the fixed error name only, never a path,
exception text, or document value.

**What it reports.** For each candidate: the recorded current and previous
original hashes, whether the version is an approved copy, unchanged since
ingestion, a new version, or has no baseline; a bounded block-level old/new text
diff (counts plus at most five excerpts); explicit `publication`, `amendment`,
`repeal`, and `validity` signals with page/section location and a bounded
excerpt of at most 280 characters (at most 50 signals per candidate); and the
potentially affected catalog sources, reviewed passages, and reviewed evaluation
cases with the reason for each link. Reported links come from the candidate's own
approved-source identity or URL, the candidate's `content_sha256`, instrument
references such as `Real Decreto 1048/2022` named in the same sentence as a
signal, passages belonging to an affected source, and passages that themselves
cite an affected instrument. Only a title that *starts* with a numbered
instrument (for example `Real Decreto 2200/2099, por el que se modifica …`) makes
that instrument the candidate's own identity; an unnumbered title such as
`Resolución de 9 de septiembre de 2099, por la que se modifica la Ley 5/2098`
keeps the `Ley 5/2098` as a target instead of dropping the link. A passage or case
can link a target instrument whose own source is absent from the catalog; that
candidate is review-required with the reason `affected_passage`, so a reported
link never coexists with `review.required: false`. The readable
contract is `knowledge/legal-change-impact.schema.json`
(`legal-change-impact-report-v1`).

**Machine-evident versus ambiguous.** A signal is `machine_evident` only when
the sentence states the action explicitly: an amendment or repeal that names a
resolvable instrument in the same sentence, a validity statement with an
explicit `d de mes de aaaa` or `dd/mm/aaaa` date, or a publication reference
that names an official bulletin together with a number or date. Triggers are
broad Spanish word stems, not a legal-action parser: `derog*`/`revoc*`/
`deja sin efecto`/`pierde vigencia` for repeal; `modific*`/`modifiq*` (including
the nouns `modificación` and `modificaciones`)/`nueva redacción`/
`se suprime|añade|adiciona` for amendment; `entra|entrada en vigor`/`prorrog*`/
`mantiene su vigencia`/`se extiende|amplía|prorroga|reduce … hasta` for
validity; and bulletin names/`se publica`/`publicado en el` for publication. A
static `el plazo … hasta …` or `la vigencia … hasta …` sentence with no change
wording is not a validity signal at all — only change wording such as
`se extiende/amplía/prorroga/reduce … hasta` plus an explicit date is. Because
the stems are broad, a document-part heading or noun phrase such as
`Disposición derogatoria única.`, `Modificaciones presupuestarias.`, or
`La modificación de las condiciones de acceso se aprueba por resolución.` is
reported as `ambiguous` and needs review; only a document part with no trigger
word, such as a bare `disposición adicional`, emits no signal. Everything else
is `ambiguous`: no named instrument, no explicit date, an incomplete publication
reference, any `U+FFFD` replacement character, or recognised negation. Negation
is sentence-scoped and limited to the listed phrasings:
`no se modifica/deroga/suprime/publica`, `sin que se modifique` (and the other
listed subjunctive verbs), `no supone/implica/conlleva una
modificación/derogación`, `no queda/quedan derogado/modificado/sin efecto`,
`no deja/n deja sin efecto`, `no pierde/n su vigencia`, `en ningún caso`,
`tampoco`, and `nunca`. Other negative wording is read as positive or missed.
Any ambiguous `publication`, `amendment`, `repeal`, or `validity` signal —
negated wording included — makes that candidate review-required
(`ambiguous_signal`), even when it links no approved source, so a negated
sentence or an unlinked blanket repeal cannot pass as "nothing to review".
Negated signals are never linked to an instrument. The rule has no
exception for an unchanged approved copy: if the approved text itself contains
wording this analyzer cannot read as machine-evident, the report keeps asking
for an author instead of deciding for it. No signal of any class authorizes
retirement; the report's `review_gate` fixes `automatic_retirement` to `false`
and `automatic_retirement_allowed` to `false` for every candidate. A candidate
that names an affected source stays review-required until a human resolves it in
the reviewed-update workflow or the operator discards it from the ingestion
state; re-running the analysis is idempotent.

**Determinism.** The report carries the SHA-256 of every input, the analyzer
version, and the supplied `as_of` date — no wall-clock timestamp. Repeated runs
over the same pinned inputs produce byte-identical output, and the file is
written atomically. Byte-identical reports are not a legal conclusion: they
reproduce the same lexical reading of the same extracted text.

**Failure and recovery.** A candidate whose ingestion status is `failed` or
`rejected` has no extracted text, so it is reported as
`version_status: no_extracted_document` with
`analysis_failure: no_extracted_document`, an empty signal list, and no review
reason: the field says why no text analysis exists, and retrying or fixing the
ingestion is owned by the ingestion state (`status`, `failure`, `attempts`), not
by this report. Per-candidate analysis failures are recorded as fixed
categories (`missing_extracted_document`, `extracted_text_mismatch`,
`malformed_extracted_document`, `size_limit_exceeded`, `internal_error`) and
never abort the other candidates; that candidate's previous good report entry is
not preserved, because the report is a derived artifact and is meant to be
regenerated. A globally invalid input exits `2` and overwrites nothing. Bounds
per candidate: 5,000 blocks / 2,000,000 characters of current text, 50 signals
(each with an excerpt of at most 280 characters), five text-diff excerpts, and
1,000 candidates per run.

**Limits.** Detection is lexical Spanish matching over extracted text, not legal
interpretation: it can miss a change phrased in unfamiliar wording, cannot
decide legal effect, and cannot resolve a conflicting or incomplete source.
Triggers are broad word stems, so a real document's static wording (`entrada en
vigor`, `prórroga`, `modificación`, a `Disposición derogatoria` heading) usually
produces an ambiguous signal: review-required may be near-universal, and that
reviewer load is the price of not silently dropping a legal change. Negation
recognition covers only the listed phrasings; other negative wording is read as
positive or missed. A static deadline sentence without change wording produces
no validity signal, so a deadline change inside such a sentence is visible only
through the text diff and `text_changed_without_signal`. Only a version recorded
by candidate ingestion is compared; discovery's `version_hash` covers only title
and URL, so bytes replaced at a stable URL without a new version are invisible
here. If the previous extracted document is missing from the quarantine, the
diff is reported as unavailable instead of guessed. A failed or rejected
ingestion is reported as `analysis_failure: no_extracted_document` with no
review reason and does not raise the gate on its own; if those are the only
unresolved candidates the CLI still exits `0`, so exit status alone does not
report the gap and the ingestion state must be checked separately. Source,
passage, and case links are string- and draft-digest based and do not establish
that a passage is still an accurate answer to any question. The report contains
bounded excerpts of official public document text for review, never an answer,
and never personal or land data; store it with the same access control as the
quarantine. Nothing in this command updates the corpus, so no legal-coverage or
answer-quality claim follows from it. Only synthetic fixtures back the feature
today; there is no live run against a published amendment and detection
precision/recall is unmeasured.

## Human-reviewed knowledge update packages

`app/review_package.py` turns one reviewed proposal over quarantined candidates
into a bounded draft review package. It is standard-library only, offline, and
read-only over `knowledge/`: `prepare` and `decide` write only under the
operator's workspace. `merge` is the only function that writes canonical
artifacts, and only after a named requested reviewer other than the author
approves and every required check still passes.

**This is a local draft, not a hosting-platform pull request.** The package is
an inspectable directory (`package.json`, `REVIEW.md`, and after review
`decisions.json`, `DECISION.md`, `merge.json`) that an operator can attach to a
real repository PR. This repository has no Git/hosting API integration, so
GitHub branch protection is **not** enforced here; the controlled `merge`
command independently verifies the recorded approval. Direct filesystem writes
to `knowledge/` remain possible for anyone with access, so keep the workspace
and canonical files access-controlled and reviewable in Git.

### Prepare

Run it from the repository root with the ingestion state and quarantine produced
by the preceding pipeline, the current approved catalog/passages, a reviewed
proposal, and at least one named reviewer:

```sh
backend/.venv/bin/python backend/scripts/knowledge_review.py prepare \
  --ingestion-state /path/to/official-ingestion-state.json \
  --quarantine /path/to/official-document-quarantine \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --proposal /path/to/knowledge-update-proposal.json \
  --cases knowledge/pac_answer_eval.json \
  --reviewer "Nombre Revisor" \
  --as-of 2026-10-27 \
  --workspace /path/to/review-workspace
```

Omit `--cases` only when the proposal makes no catalog or passage change: a
proposal that changes the reviewed corpus requires the reviewed case set. With
`--cases`, preparation validates both the current and the **after-state**
catalog/passages against it, records the case-set digest in the package, and
blocks readiness with `proposal_evaluation_impact: orphaned_cases:<ids>` when a
removal or replacement would leave a reviewed case without its expected source
or passage. Without `--cases`, any change is blocked with
`proposal_evaluation_impact: cases_unavailable`; a no-op proposal still passes.
`--workspace` must stay outside the repository `knowledge/` directory. `prepare`
writes `<workspace>/<package_id>/package.json` and `REVIEW.md`; canonical
knowledge is byte-identical afterwards. It exits `0` when `merge_readiness` is
`ready_for_review`, `1` when any automated check failed
(`needs_human_attention`), and `2` on invalid input, a non-human/self reviewer,
a reviewer outside the requested set, or another refused gate.

The proposal contract is `knowledge-update-proposal-v1`: `summary`, 1–20
`candidates` (each a 64-character id from the ingestion state, with optional
`resolution` `{findings, note}` and `unknown_fields`), `catalog` and `passages`
sections `{add, update, remove}`, optional `author` (defaults to the preparer
automation identity), `links` mapping every added, updated, or removed catalog
source and every passage change to its selected candidate, and optional
`unresolved_questions`. A proposal cannot exceed the candidate bound, link to a
candidate it did not select, or introduce an unknown field outside `validity`
and `applicability`. A passage edit or removal without exactly one
source-to-candidate link fails `proposal_provenance`.

The package records source URL/issuer/registry provenance, observation and
retrieval times, original and extracted hashes and locations, page/section
counts, a bounded old/new text diff and signal excerpts, proposed catalog and
passage changes, affected sources/passages/evaluation cases, every automated
check, unresolved questions, and explicit limits. Source document text is
rendered only as fenced evidence, never as instructions. Unknown validity and
applicability stay absent; a proposal that writes a literal unknown value,
omits provenance, links a different candidate hash/URL, misstates the extracted
digest, or leaves an ambiguous impact finding unresolved becomes
`needs_human_attention` and cannot be approved.

The package also binds the evaluation-case digest and the after-state check
result (`proposal.evaluation`), and its after hashes use the catalog/passages'
existing field order for entries the proposal does not rewrite rather than
sorting every entry; a newly added or rewritten entry follows the proposal's
own serialization. The readable contracts
are `knowledge/knowledge-update-review.schema.json` (package) and
`knowledge/knowledge-update-review-decisions.schema.json` (decision history).
An orphaned evaluation case blocks readiness. Affected and rewritten cases are
embedded as **report-only**: they are not re-run and are not a pass/fail gate or
a quality claim.

### Decide

A named human other than the proposal author records one decision:

```sh
backend/.venv/bin/python backend/scripts/knowledge_review.py decide \
  --package-dir /path/to/review-workspace/<package_id> \
  --reviewer "Nombre Revisor" \
  --decision approve \
  --decided-on 2026-10-28 \
  --note "Original y texto extraído comparados."
```

`--decision` is `approve`, `request_changes`, or `reject`. Approval is refused
for a known automation/CI identity (`reviewer_not_human`: `ci`, `cd`, `ci/cd`,
`actions`, `github-actions`, `workflow`, `pipeline`, `automation-*`,
`service-account`, `preparer`, bot names), a reviewer the package did not
request (`reviewer_not_requested`), the proposal author (`self_approval`), a
package with failing checks or `needs_human_attention` (`approval_blocked`), or
a stale package/check digest (`stale_approval`). A green CI result, label, or
matching hash is never approval. The identity list is a denial list, not
authentication: local records cannot prove who typed a name. Every decision is
appended to `decisions.json` and `DECISION.md`; a later `request_changes` or
`reject` revokes an earlier approval. A revised proposal produces a new package
id with new checks and no inherited approval.
`decide` exits `0` on a recorded decision, `2` on any refusal; after a merge it
refuses with `already_merged`.

### Merge

```sh
backend/.venv/bin/python backend/scripts/knowledge_review.py merge \
  --package-dir /path/to/review-workspace/<package_id> \
  --catalog knowledge/source_catalog.json \
  --passages knowledge/passages.json \
  --cases knowledge/pac_answer_eval.json
```

`merge` writes canonical artifacts only when the effective decision is
`approved`, the checks digest still matches, the approver is a named requested
human other than the author, readiness is `ready_for_review`, and the current
canonical bytes still match the package's recorded `before` hashes. When the
package recorded a case-set digest, `--cases` is mandatory (`cases_required`)
and the file must still hash to that digest (`evaluation_cases_drift`);
`merge` then revalidates the after-state against those cases, so editing the
cases after preparation cannot bypass the gate. It revalidates the resulting
catalog/passages as of the **approval date**, recomputes `after` hashes without
reordering entries, writes both files atomically, and records `merge.json` with
`reindex_required: true`, `reindexed: false`, and `released: false`. Canonical
drift, a tampered package/decision, an expired source, changed cases, or an
invalid result refuses with exit `2` and writes nothing. A second merge is
refused (`already_merged`). A no-op proposal leaves both canonical files
byte-identical.

**Merge is not release.** It never reindexes, releases, or deploys. The separate
reindex/release feature owns index rebuilds, artifact/model versions, rollback,
and the plainly stated corpus boundary. An approved bounded update is not
legal-coverage or answer-quality certification.

### Limits

- The local package is not a hosted PR, so host-enforced merge protection and
  reviewer assignment do not exist; the `merge` command is the procedural gate.
- Reviewer identity and decisions are plain local records, not cryptographic
  signatures. The commands refuse known automation identities and
  self-approval, require an approver from the package's `requested_reviewers`,
  and bind decisions to the package/checks digest, but identities are not
  authenticated and a malicious operator can still edit the workspace or
  canonical files directly.
- Original-byte verification requires the quarantined original to still exist.
  A missing copy is a reviewer question, not an automated comparison; only a
  person can compare the extracted text with the official original.
- A proposal that changes the reviewed corpus requires the reviewed evaluation
  case set, and merge must receive the same digest-bound file. Evaluation cases
  are validated for references, not re-run; removing or rewriting a referenced
  source/passage blocks readiness until a human updates the cases in a separate
  reviewed change. A no-op proposal is allowed without cases.
- Review display is bounded (at most 40 change entries and truncated field
  values/excerpts); open large documents in the quarantine for a full reading.
- Canonical after hashes and merge writes preserve the catalog/passages' field
  order. A proposal input is normalized through the package's sorted JSON, so a
  newly added entry's own keys are sorted while every existing entry keeps its
  reviewed order. Only a real change alters the file; an empty proposal leaves
  it byte-identical.
- Extraction inherits the standard-library PDF/HTML limits above (no OCR,
  encrypted/scanned documents fail closed, subset-font maps can leave `U+FFFD`).
- Workspace, decisions, and quarantine evidence are retained by the operator
  and are never garbage-collected. Deleting them makes an old package's
  evidence unrecoverable.
- Merge writes the catalog and passages atomically one file at a time, not as a
  single transaction. An OS failure between the two writes (or before
  `merge.json` is written) can leave the pair inconsistent; the package then
  refuses with `canonical_drift`. Restore both Git-tracked files or reapply the
  approved merge before retrying.
- Review turnaround and reviewer availability are manual; nothing expires an
  unapproved package. A pending package simply never merges.
- Only synthetic fixtures back this flow today; there is no live run against a
  real published update.
