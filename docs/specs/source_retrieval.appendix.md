# Appendix — `source_retrieval`

Planning and verification record for [`docs/specs/source_retrieval.md`](source_retrieval.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/source_retrieval.md` remains the authoritative
acceptance record.

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
