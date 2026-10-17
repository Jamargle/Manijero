# Feature Spec: `source_retrieval`

## Source metadata

- Feature: `source_retrieval` — Search reviewed source passages
- Area: backend
- Depends on: `source_catalog_validation` (accepted)
- Feature-list behavior: a question retrieves relevant passages from the reviewed corpus with enough metadata to identify the source and its applicability.
- Feature-list verification: run source-anchored questions and confirm the expected source passage appears in the returned candidates.
- Feature-list note: start with a measured retrieval baseline before treating candidate thresholds as release gates.
- Scope size: one passage data model plus one offline retrieval flow; correctly sized.

## Goal

Provide a dependency-free, offline retrieval boundary that, given a plain-Spanish question, returns ranked candidate passages drawn only from **human-reviewed** documents whose provenance is already approved by the accepted source-catalog gate, together with enough metadata (source identity, location, dates, applicability, excerpt) to identify the source and its applicability. Establish a **measured** retrieval baseline (hit@k / MRR) on a small source-anchored evaluation set built from synthetic reviewed test passages, because the canonical catalog is intentionally empty and no ingestion/chunking pipeline exists.

## Non-goals

- Ingestion, download, parsing, OCR, chunking, embedding, vector stores, or automated/unreviewed corpus creation.
- Any network access, model provider, LLM call, prompt, generation, or `/ask` route.
- Applicability-based filtering or land-context selection; this feature only surfaces applicability metadata (filtering belongs to `minimal_land_context` / `land_clarification`).
- Client/Compose UI, contract changes, or `contracts/openapi.yaml` changes; the existing `AnswerSource` fields are reused, not redefined.
- Adding real legal documents or asserting any legal fact. All retrieval fixtures are synthetic, clearly labeled, and contain no real deadlines, amounts, or article claims.
- Treating baseline metrics as release gates. Thresholds are reported, not enforced.

## Job story

When a reviewed passage corpus exists, I want an offline retriever that only ever searches human-approved, current, unexpired sources, so that a later generation step can ground answers in traceable evidence — and I want a reproducible baseline run so the team can calibrate thresholds from measured numbers instead of inherited guesses.

## Acceptance scenarios

### Relevant question returns the expected passage

Given a fixture catalog of approved, current sources and a reviewed passage set referencing them, when a source-anchored fixture question is searched with candidate window `k`, then the expected passage appears in the returned candidates at rank ≤ `k`, ranked above unrelated passages.

### Candidates carry identifying metadata

Given a matching candidate, when it is returned, then it exposes the passage id, the source id, title, issuing body, official URL, location, publication/update date, verification date, applicability, the passage excerpt, and its score/rank — field names and semantics compatible with the accepted `AnswerSource` contract.

### Unreviewed or ineligible evidence is never returned

Given a passage whose source id is unknown, or whose source is not `approved`, not `current`, or expired as of the supplied `--as-of` date, when retrieval runs, then that passage is not returned (ineligible sources are excluded and counted; an unknown source id is a located load error), and retrieval never falls back to unreviewed content.

### Empty retained corpus returns no candidates

Given the canonical repository catalog is empty and no reviewed passage set is supplied, when retrieval runs, then it returns zero candidates without inventing evidence.

### Spanish, accent- and case-insensitive matching

Given a question that differs from the passage only in case or written accents (for example `solicitud unica` vs `solicitud única`), when it is searched, then the passage still matches.

### Reproducible measured baseline

Given the fixture catalog, passage set, and evaluation questions, when the baseline command runs with an explicit `--as-of` and `--k`, then it prints each question's expected-passage rank plus aggregate `hit@k` and MRR, and the run is deterministic across repeated invocations.

## Repository research

Inspected:

- `feature_list.json`: `source_retrieval` is `not_started`, depends on accepted `source_catalog_validation`, and its note requires a measured baseline before thresholds.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md`: approved official material only for regulatory claims; sources need a stable link, issuing body, relevant location, and verification date; abstain when evidence is inadequate; evaluation size/metrics/thresholds are set after a measured baseline.
- `docs/specs/source_catalog_validation.md` and `docs/validations/source_catalog_validation.md`: the accepted gate, its fixture/test conventions, `--as-of` determinism, no-network guarantee, and the explicit handoff of the validated catalog to `source_retrieval`.
- `backend/app/source_catalog.py`, `backend/scripts/validate_source_catalog.py`, `backend/tests/test_source_catalog.py`, `knowledge/source_catalog.schema.json`, `knowledge/README.md`: standard-library, strict-key, fail-closed validation; approved hosts/issuers; `review_status: approved`, `lifecycle_status: current`, `valid_until` expiry; synthetic fixtures under `backend/tests/fixtures/source_catalog/`.
- `contracts/openapi.yaml` (`AnswerSource`: `title`, `issuing_body`, `url`, `location`, `published_or_updated_on`, `verified_on`, `excerpt`) and `docs/specs/answer_api_contract.md`: the existing source shape to reuse.
- `backend/app/main.py`, `backend/README.md`, `backend/requirements.txt`: only `/health` exists; pytest is the backend convention; no retrieval, corpus, embedding, or vector dependency is present.
- `MasterPlanV3.md` §§6.1–6.3, 9.1–9.2, 11.3: planned legal-structure chunking, mandatory chunk metadata, hybrid search with metadata filters, and retrieval `hit@k` / MRR evaluation on a golden set with thresholds calibrated against a measured baseline.
- `scripts/init.sh`: verifies KMP targets only; it has no backend/retrieval command.

No ingestion, passage/chunk model, retrieval code, embedding client, vector store, golden dataset, or persistent E2E command exists today. `knowledge/source_catalog.json` is valid and intentionally empty (0 sources). `ARCHITECTURE.md`, `CONSTRAINTS.md`, `docs/technical-discovery.md`, `docs/mvp-scope.md`, and the skill's template file are absent.

## Technical approach

### Passage-set contract

Add a readable, versioned contract `knowledge/passages.schema.json` (`passage-set-v1`) mirroring the catalog-schema style, plus its strict in-code validator. A passage-set document is:

```json
{
  "schema_version": "passage-set-v1",
  "passages": [
    {
      "id": "fixture-rd1048-art1-p1",
      "source_id": "rd_1048_2022",
      "location": "Art. 1",
      "text": "Fragmento sintético de prueba; no afirma ningún plazo real.",
      "critical": false,
      "applicability": { "crop": "olivar", "water_regime": "dryland" }
    }
  ]
}
```

Rules: top level has only `schema_version` and `passages`; every passage has non-blank `id` (unique), `source_id`, `location`, and `text`, plus optional `critical` (boolean) and `applicability` (same value rules as the catalog: `crop` non-blank, `water_regime` ∈ dryland/irrigated/mixed, `production_method` ∈ conventional/organic/mixed; omit unknown values). Unknown keys are rejected. The passage set is a Git-tracked, human-reviewed artifact. This feature ships the contract and fixtures only; the canonical `knowledge/passages.json` will be produced by a later reviewed ingestion feature, so no canonical passage file is created now.

### Retrieval index and scoring

Implement `backend/app/retrieval.py` as a pure, standard-library module (`json`, `re`, `math`, `unicodedata`, `dataclasses`, `datetime`):

- `tokenize(text)`: lowercase, strip diacritics via NFKD, split on non-alphanumerics, drop a small built-in Spanish stopword list.
- `Bm25Index`: BM25 with `k1 = 1.5`, `b = 0.75` over passage `text`; deterministic ordering with ties broken by passage `id`.
- `Retriever`: built from a catalog document, a passage-set document, and an `as_of` date; exposes `search(question, k=...) -> tuple[RetrievedPassage, ...]`.
- `RetrievedPassage`: `passage_id`, `source_id`, `title`, `issuing_body`, `url`, `location`, `published_or_updated_on`, `verified_on`, `excerpt`, `applicability`, `critical`, `score`, `rank`. Field names/semantics line up with the accepted `AnswerSource` so `grounded_answer_generation` can reuse them without redefining the contract.

A question with no tokens returns an empty tuple. Empty corpus, absent matches, and out-of-vocabulary questions return fewer than `k` candidates or none; retrieval never fabricates a passage.

### Eligibility and provenance

The retriever is a consumer of the accepted catalog gate:

- It reuses `validate_catalog` from `backend/app/source_catalog.py`; if the catalog is invalid it refuses to build an index (fail closed) rather than indexing partially approved data.
- A passage is indexed only when its `source_id` resolves to a catalog source that is `review_status: approved`, `lifecycle_status: current`, and not expired as of `as_of`. Ineligible sources are excluded from the index and reported as a count.
- A passage whose `source_id` does not exist in the catalog is a located load error (`PassageSetError` with a JSON path such as `$.passages[0].source_id`), never a silent skip.
- The loader never performs network access; tests enforce this with a socket guard.

### Baseline evaluation harness

Add `backend/scripts/evaluate_retrieval.py`, an offline CLI mirroring `validate_source_catalog.py`:

```
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints, per question, the expected-passage rank(s), then aggregate `hit@k`, `recall@k`, and MRR, with an optional `--json` mode. The eval file is JSONL: `{"question": "...", "expected_passage_ids": ["..."]}`. Exit codes: `0` report produced, `2` unreadable/invalid input. An explicit `--fail-on-miss` flag may exit `1` on a miss, but it is **off by default**: the feature-list note says candidate thresholds are not release gates yet.

## Expected file changes

- Create `knowledge/passages.schema.json` — versioned `passage-set-v1` readable contract.
- Create `backend/app/retrieval.py` — passage loading/eligibility, Spanish tokenizer, BM25 index, `Retriever`, `RetrievedPassage`.
- Create `backend/scripts/evaluate_retrieval.py` — offline baseline CLI (report-only by default).
- Create `backend/tests/test_retrieval.py` — focused tests.
- Create `backend/tests/fixtures/retrieval/` — fixture catalog (approved synthetic sources), reviewed synthetic passage set, JSONL evaluation questions, plus edge cases: unknown `source_id`, unknown key, malformed JSON, and an expired source.
- Update `knowledge/README.md` — document the passage-set contract, eligibility coupling to the catalog, and the baseline command.
- Update `backend/README.md` — note the offline retrieval module and baseline script (keep `/health` as the only route).
- Update `feature_list.json` and `PROGRESS.md` after implementation/validation with actual status, commands, and the measured baseline numbers. This planning pass records the spec link only.

`scripts/init.sh`: no change. It checks and verifies KMP targets only, so this backend/knowledge feature is verified with the documented Python commands instead of adding a long-running or KMP-coupled step to the wrapper.

No changes to `knowledge/source_catalog.json`, `backend/app/source_catalog.py`, `contracts/`, `backend/app/main.py`, or any client/shared code.

## Visual design impact

None. This is an offline backend boundary; it adds no Compose UI and no user-facing Spanish copy.

## Durable documentation impact

- `knowledge/README.md`: update; it is the durable operational contract for how reviewed passages relate to the approved catalog and how to run the baseline.
- `knowledge/passages.schema.json`: create; the durable, versioned passage format.
- `AGENTS.md`, `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`: no update; existing source-grounding, review, and UI rules already govern this work.
- `MasterPlanV3.md`: no update; it is planning context, while the schema/README become executable documentation.
- `ARCHITECTURE.md`, `CONSTRAINTS.md`: not needed; both are absent and this focused offline boundary does not establish a broader runtime architecture.
- `PROGRESS.md` and `feature_list.json`: update after verification, recording the measured fixture baseline and stating plainly that it is synthetic, not a legal-quality claim.

## Implementation plan and tasks

1. Add `knowledge/passages.schema.json` with strict `passage-set-v1` fields, mirroring the catalog schema style; document it in `knowledge/README.md`.
2. Implement `backend/app/retrieval.py`: strict passage-set loading with located errors, catalog revalidation, eligibility/expiry filtering, Spanish tokenizer, deterministic BM25 scoring, `Retriever`, and `RetrievedPassage` mapping to the accepted `AnswerSource` fields.
3. Add the fixture catalog, reviewed synthetic passage set, and JSONL evaluation questions under `backend/tests/fixtures/retrieval/`; include edge fixtures for unknown `source_id`, unknown key, malformed JSON, and an expired source.
4. Implement `backend/scripts/evaluate_retrieval.py` with deterministic `--as-of`, `--k`, per-question ranks, aggregate `hit@k`/`recall@k`/MRR, `--json`, and report-only default exit behavior.
5. Add `backend/tests/test_retrieval.py`: tokenizer behavior, ranking with a clear best match, deterministic tie-break, metadata mapping, unknown-source error, expired and non-approved exclusion, invalid-catalog refusal, empty-corpus no-candidates, no-network socket guard, and CLI report/exit-code coverage.
6. Run the baseline CLI and the focused/regression suites; record the measured `hit@k`/MRR numbers and only the commands actually run.
7. Update `feature_list.json` and `PROGRESS.md` with status and evidence; state that fixtures are synthetic and thresholds are not release gates.

## Verification plan and evidence

Run from the repository root:

```sh
python3 backend/scripts/validate_source_catalog.py backend/tests/fixtures/retrieval/catalog.json --as-of 2026-10-13
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
cd backend && python -m pytest tests/test_retrieval.py
cd backend && python -m pytest
git diff --check
```

Capture: the fixture catalog validating (exit 0); per-question expected-passage ranks and aggregate `hit@5`/MRR as the measured baseline; focused and full pytest counts; the canonical empty corpus returning zero candidates; and confirmation that no network call occurs. Record the baseline in `PROGRESS.md`. No browser, API, or E2E test is required because the feature has no user-facing or API flow and no persistent E2E framework; retrieval ranking is covered by unit tests and the baseline script.

## Validator checklist

- [ ] `knowledge/passages.schema.json` is versioned, tracked, and matches the in-code validator (strict keys, unique ids, applicability values).
- [ ] A source-anchored fixture question returns its expected passage within rank `k`, above unrelated passages.
- [ ] Returned candidates expose the source identity, location, dates, applicability, excerpt, and score/rank with contract-compatible fields.
- [ ] Passages referencing unknown source ids fail with a located error; passages whose source is not approved, not current, or expired are excluded, never silently returned.
- [ ] The retriever refuses an invalid catalog and performs no network access (socket-guard test).
- [ ] The canonical empty catalog yields zero candidates with no invented evidence.
- [ ] The baseline command is deterministic with explicit `--as-of`/`--k`, reports `hit@k`/MRR, and does not fail the build by default.
- [ ] Fixtures are synthetic, labeled as such, and contain no real deadlines, amounts, or legal claims; no canonical passage corpus is added.
- [ ] No `/ask`, LLM, client UI, contract, catalog-validator, or unrelated files are changed; `feature_list.json`/`PROGRESS.md` report only verification actually performed.

## Risks and handoff notes

The baseline measures lexical ranking quality on a tiny synthetic fixture set; it is not evidence about legal coverage, correctness, or real Spanish user questions. Missing ingestion means the passage model is exercised only by fixtures, so the schema may need review when a real parser/chunker lands. Lexical-only retrieval may underperform on synonyms and acronyms; the `Retriever` boundary is intentionally narrow so a later hybrid (vector + BM25 + RRF) implementation can replace `search` without changing consumers. Hand off the ranked `RetrievedPassage` shape and eligibility rules to `grounded_answer_generation`, and keep applicability filtering deferred to `minimal_land_context` / `land_clarification`.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5
./scripts/init.sh --backend-tests tests/test_retrieval.py
```
<!-- verify:end -->

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/source_retrieval.md.
- Added knowledge/passages.schema.json (readable passage-set-v1 contract), backend/app/retrieval.py (strict passage-set validator with located errors, Spanish case/diacritic tokenizer, deterministic BM25 k1=1.5/b=0.75 index, Retriever, RetrievedPassage mapped to AnswerSource field names), backend/scripts/evaluate_retrieval.py (offline report-only baseline CLI), backend/tests/test_retrieval.py (76 focused tests), and synthetic fixtures under backend/tests/fixtures/retrieval/ (approved catalog, 12 reviewed passages, 7 JSONL questions, plus unknown-source, unknown-key, bad-applicability, malformed-JSON, expired, not-approved, and not-current edge cases).
- python3 backend/scripts/validate_source_catalog.py backend/tests/fixtures/retrieval/catalog.json --as-of 2026-10-13 -> exit 0, 'schema source-catalog-v1, 3 source(s) checked as of 2026-10-13'.
- python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5 -> exit 0; MEASURED BASELINE hit@5 = 0.857 (6/7), recall@5 = 0.857, MRR = 0.857; 3 eligible sources, 12 indexed passages, 0 excluded. Six source-anchored questions return their expected passage at rank 1 (including an unaccented 'solicitud unica' variant); one deliberate synonym probe ('¿Quién puede pedir las ayudas?' vs the 'titular de la explotación' passage) misses, which is the honest lexical-only limitation.
- The baseline is deterministic: two --json runs are byte-identical (diff clean), and repeated in-process searches return identical (id, rank, score) tuples.
- Canonical empty corpus: python3 backend/scripts/evaluate_retrieval.py --catalog knowledge/source_catalog.json --as-of 2026-10-13 --k 5 -> exit 0 with 0 eligible sources, 0 indexed passages and no questions; with --eval and no --passages every question returns zero candidates (hit@5 = 0.0) and no invented evidence.
- Fail closed and no-network: an expired (valid_until 2026-01-01), non-approved (review_status pending), or non-current (lifecycle_status repealed) catalog raises CatalogRejectedError and the CLI exits 2; an unknown passage source_id is a located error at $.passages[0].source_id; a socket-guard test blocks socket.socket and still builds the index and searches.
- Commands actually run: cd backend && python -m pytest tests/test_retrieval.py -> 76 passed; cd backend && python -m pytest -> 121 passed (76 new + 45 existing); python3 -m py_compile on the three new Python files; git diff --check clean. The worktree has no `python` on PATH and no pytest in the system interpreter, so pytest ran via a temporary venv (`python -m pytest` with the venv interpreter); no dependency was added to the repo.
- Not run: Android/Desktop/Gradle checks (not applicable to this backend/knowledge feature), and no browser/API/E2E test (no user-facing or API flow, and no persistent E2E framework exists).
- Synthetic-only and report-only: no canonical passages.json was created, no real legal document or deadline/amount/article claim was added, thresholds are not enforced (--fail-on-miss is off by default), and contracts/, knowledge/source_catalog.json, backend/app/source_catalog.py, backend/app/main.py and all client code are unchanged. Ready for independent validation.
- Independent validator ACCEPTED this feature (2026-10-13, record: docs/validations/source_retrieval.md). It independently reproduced the fixture catalog gate (exit 0, 3 sources), the measured baseline hit@5 = 0.857 (6/7) / recall@5 = 0.857 / MRR = 0.857, the per-question ranks including the disclosed synonym miss, determinism (byte-identical --json runs, hash-seed and corpus-order independence), hand-recomputed metrics, k-window semantics, the empty-corpus zero-candidate case, and fail-closed exits 2 with located paths for expired/non-approved/non-current catalogs and unknown source_id/keys. It confirmed no-network behavior with a stricter independent socket/DNS/TLS guard and a blocked-socket CLI subprocess, verified the schema/validator sync, the synthetic-only fixtures with no real legal facts, and that pytest ran (76 focused, 121 full) in a venv outside the repo with no dependency added. Scope confirmed: contracts/, catalog validator, /health-only service, client code, and scripts/init.sh untouched; non-blocking findings F1-F4 recorded.
