# Validation: source_retrieval

## Verdict

**Accept** — independently validated against `docs/specs/source_retrieval.md`
on 2026-10-13. No repair required.

## Evidence

- Fixture catalog gate:
  `python3 backend/scripts/validate_source_catalog.py backend/tests/fixtures/retrieval/catalog.json --as-of 2026-10-13`
  exited 0: `schema source-catalog-v1, 3 source(s)`.
- Measured baseline reproduced exactly:
  `python3 backend/scripts/evaluate_retrieval.py --catalog backend/tests/fixtures/retrieval/catalog.json --passages backend/tests/fixtures/retrieval/passages.json --eval backend/tests/fixtures/retrieval/eval_questions.jsonl --as-of 2026-10-13 --k 5`
  exited 0 with `hit@5 = 0.857 (6/7)`, `recall@5 = 0.857`, `MRR = 0.857`, 3 eligible
  sources, 12 indexed passages, 0 excluded — matching the recorded numbers.
- Per-question ranks re-derived: six source-anchored questions return their expected
  passage at rank 1 (including the unaccented `solicitud unica` variant); the deliberate
  synonym probe `¿Quién puede pedir las ayudas?` misses
  (`fixture-p-titular-1 not retrieved within k=5`), which is the honest lexical-only gap.
- Metric honesty: `hit@k`, `recall@k`, and MRR recomputed by hand from the `--json`
  report are identical; per-question `hit`/`recall`/`reciprocal_rank` are internally
  consistent and all returned ranks are `<= k`.
- Window semantics: an expected-at-rank-2 question yields `not retrieved within k=1`
  (`hit@1 = 0.000`) at `k=1` and rank 2 (`hit@2 = 1.000`) at `k=2`; a two-expected
  question yields `recall@1 = 0.5` / `recall@5 = 1.0`.
- Determinism: two `--json` runs are byte-identical, identical under differing
  `PYTHONHASHSEED`, and ranking is independent of passage-set order (shuffled corpus →
  identical id/rank/score).
- Empty retained corpus: the canonical `knowledge/source_catalog.json` yields 0 eligible
  sources, 0 indexed passages, and no candidates; with `--eval` and no `--passages` every
  question returns `[]` and `hit@k = 0.0` with no invented evidence.
- Fail closed: expired (`valid_until 2026-01-01`), non-approved (`review_status pending`),
  and non-current (`lifecycle_status repealed`) catalogs exit 2 with located paths
  `$.sources[0].valid_until` / `.review_status` / `.lifecycle_status`; an unknown passage
  `source_id` exits 2 with `$.passages[0].source_id`; an unknown key exits 2 with
  `$.passages[0].excerpt`; a bad applicability value exits 2 with
  `$.passages[0].applicability.water_regime`; malformed JSON, a missing input, an invalid
  `--as-of`, and `--k 0` all exit 2.
- Report-only default: with no flag the run exits 0 despite the one miss; `--fail-on-miss`
  exits 1. Thresholds are not enforced.
- No network: an independent, stricter guard (patching `socket.socket`,
  `create_connection`, `getaddrinfo`, `gethostbyname`, and `ssl.wrap_socket` before import)
  plus a blocked-socket CLI subprocess both built the index and searched successfully;
  neither new module imports `socket`, `urllib`, `requests`, or `httpx`.
- BM25 correctness: hand-computed single/duplicate-term scores match standard Okapi BM25
  with `k1=1.5`, `b=0.75`; ties break by passage id. Tokenizer behavior verified, including
  `solicitud única ≡ SOLICITUD unica`.
- Metadata mapping: returned fields (`title`, `issuing_body`, `url`,
  `location`, `published_or_updated_on`, `verified_on`, `excerpt`, plus `passage_id`,
  `source_id`, `applicability`, `critical`, `score`, `rank`) match the accepted
  `AnswerSource` shape in `contracts/openapi.yaml`; applicability/`critical` fall back
  passage→source and are copied, not aliased; input dicts are never mutated.
- Schema/validator sync: version constant, required/optional key sets,
  `additionalProperties:false`, applicability enums, `minProperties:1`, and id patterns all
  agree between `knowledge/passages.schema.json` and `backend/app/retrieval.py`.
- Fixture safety: every source title contains "fixture"/"no es una norma real" and every
  passage text starts `Fragmento sintético de prueba`; a test guard forbids digits, `€`, or
  `%` in excerpt text, so no real deadline, amount, or article claim exists.
- Tests: `pytest tests/test_retrieval.py` → 76 passed; full `pytest` → 121 passed
  (76 new + 45 existing). Pytest ran in a temporary virtualenv created outside the
  repository; `backend/requirements.txt` was not changed, so no dependency was added to the
  repo.
- `git diff --check` clean; `py_compile` clean on the three new Python files.

## Scope and security review

The change adds an offline, standard-library retrieval boundary plus its passage schema,
baseline CLI, tests, and synthetic fixtures. Scope was confirmed clean against the spec:
`contracts/`, `knowledge/source_catalog.json`, `backend/app/source_catalog.py`,
`backend/app/main.py`, `backend/requirements.txt`, all client/shared code, `init.sh`,
`AGENTS.md`, `DESIGN.md`, and `MasterPlanV3.md` are untouched; `/health` remains the only
route; `knowledge/passages.json` is deliberately absent. No network client, credentials,
secrets, LLM/provider call, `/ask` route, logging, or unreviewed corpus was introduced.
Diagnostics contain only JSON paths and rule text, never field values or excerpt content;
the baseline report emits question text and passage ids only. No blocking security or
privacy findings were identified.

## Findings

Non-blocking:

- **F1 (low, informational).** `excluded_passages_ineligible_source` is always 0 for any
  catalog that passes the accepted gate, because `validate_catalog` already rejects
  non-approved/non-current/expired sources before per-passage exclusion runs. The predicate
  is real and unit-tested; this is design redundancy, not a defect, and the acceptance
  scenario holds in its stronger fail-closed form.
- **F2 (low, optional wording).** `PROGRESS.md` line 8 "Retrieval … remain deferred"
  describes the client chat boundary and is still true in context, but reads awkwardly next
  to the new retrieval line. A one-line clarification is optional.
- **F3 (low, optional follow-up).** `init.sh --check`'s banner still lists retrieval as
  deferred; the spec mandates `init.sh`: no change, so a refresh would be separate
  housekeeping.
- **F4 (low, optional hardening).** An eval line naming a nonexistent passage id is counted
  as a miss (exit 0) and only visible in the human report. A warning or exit-2 check would
  make the harness harder to fool; not required by the spec.

## Residual uncertainty

The baseline measures lexical BM25 ranking on a tiny, implementer-authored synthetic fixture
set. It is a calibration starting point, not evidence about legal coverage, correctness, or
real Spanish user questions; thresholds remain unenforced. Because no ingestion pipeline
exists yet, the passage model is exercised only by fixtures and may need review when a real
parser/chunker lands. Android/Gradle/E2E checks do not apply to this backend/knowledge
feature and were not run.
