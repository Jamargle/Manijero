# Rewrite colloquial olive-grower wording to official terms with a reviewed glossary

## Source metadata

- `id`: question_rewriting · `area`: backend · `depends_on`: backend_ask_endpoint, domain_procedure_map, local_notice_pipeline (all accepted) · `status` at planning: not_started
- User-visible behavior: no app or wire change. When a grower's question contains a colloquial word the owner has approved (for example "papeleo"), `/ask` searches with the grower's words plus the approved official term, so plain wording finds the same reviewed passages as official wording. The owner lists proposed pairs and approves or rejects each with one named command.
- Verification: offline pytest, a no-regression `check` over the reviewed cases and approved golden items, then the owner review walkthrough; commands in Focused verification.
- Notes (owner decisions 2026-11-08, binding):
  1. Glossary source: seed from the `local_notice_pipeline` review file plus the golden set's colloquial items. The owner approves or rejects every colloquial -> official pair in a review file before use; only approved pairs are applied.
  2. Glossary only: deterministic term expansion before retrieval. No LLM rewriting step (a model-rewriting step is a possible later feature; `colloquial_ab_evaluation` compares later).
  3. Apply mode: expand the query by appending the official term and keep the grower's original words; never replace.
- Planning interpretations (flag to owner if wrong): (a) acceptance is validator accept plus an owner review walkthrough, mirroring `golden_dataset_expansion`; (b) no real `notice-review.json` exists in the repository, so the notice seed comes from a committed review file built from the invented `local_notice_pipeline` fixtures, and the same `seed` command imports a real review file later; (c) expansion is on by default and `MANIJERO_QUESTION_GLOSSARY=off` disables it, giving `colloquial_ab_evaluation` its no-rewriting baseline.

## Goal

Close the vocabulary gap between how growers ask and how official sources are written, without letting any unreviewed wording, model output, or replaced word reach the answer path: a reviewed, deterministic, append-only expansion of the retrieval query only.

## Non-goals

- No model rewriting, synonyms, stemming, typo correction, or fuzzy matching; no pair the owner has not approved.
- No change to the question used for screening, the year check, scope guard, presupposition check, drafting payload, cache key text, trace, retention, or response; no `contracts/` or app change.
- No change to release gates, `knowledge/`, the catalog, passages, eval files, releases, or indexes; release gates stay glossary-free.
- No A/B report, metric, threshold, or evaluator flag (`colloquial_ab_evaluation`); no quality claim.
- No change to `notice_pipeline.py`; no new dependency, network, or model call.

## Job story

When a grower asks "¿Cómo se manda el papeleo de la PAC?", I want the search to also look for the official words I approved, so the reviewed passage is found without the grower having to know legal vocabulary and without anything being said in their name.

## Acceptance Scenarios

### 1. Approved pairs expand only the retrieval query, appending

Given `backend/config/question_glossary.json` with an approved pair (`papeleo` -> `solicitud`) · When `/ask` receives a question containing "papeleo" · Then every `Retriever.search` call (clarification, abstention, generation) receives `<original question> solicitud`, the original words unchanged and first; the screen, year check, scope guard, presupposition check, drafting payload, cache-key text, trace, retention, and response see only the original question; the response shape is unchanged. The same holds in hybrid mode: the ranker gets the expanded query.

### 2. Only approved pairs apply; none approved means today's behavior

Given entries in `proposed` or `rejected` state only, or no matching approved pair · When `/ask` runs · Then the search query equals the original question and responses and cache identities are byte-identical to before this feature.

### 3. Matching is deterministic, whole-token, and bounded

Given approved pairs · Then matching uses `retrieval.tokenize` on both sides (case, accents, Spanish stopwords folded) and fires only on a contiguous token sequence ("papeles" never matches "papelería"); at one position the longest colloquial wins and matches do not overlap; an official term whose tokens already occur in the question, or already appended, is skipped; at most 4 official terms are appended, in order of first match; the same question always gives the same query, and expanding an expanded query adds nothing.

### 4. A bad glossary or the off switch fails closed to no expansion

Given the glossary file missing, unreadable, over 256 KiB, not `question-glossary-v1`, or with any invalid entry (scenario 6 rules), or `MANIJERO_QUESTION_GLOSSARY=off`, or a value other than `on`/`off` · When the service starts · Then expansion is off for the whole process, `/ask` and `/ready` behave as before, and one `question_glossary` operational log line carries `state=off` and a fixed reason code (`approved=<count>` when on), never a term.

### 5. The cache cannot serve an answer found with another glossary

Given expansion on with approved pairs · Then the cache's model identity carries the retrieval mode plus `+glossary:<first 12 hex of SHA-256 of the canonical approved pairs>`; with expansion off or no approved pairs it is unchanged.

### 6. Seeding adds proposals only, screened

Given a `notice-review-v1` file · When `glossary_review.py seed --notice-review PATH` runs · Then each merged vocabulary pair not already present (by token sequences) is added as `proposed` with origin `{"kind": "notice", "ref": <first 12 hex of the file SHA-256>}`; existing entries and decisions are untouched; pairs failing the entry rules are skipped and only counted; a repeat run adds nothing; a damaged or wrong-schema file exits `2` and writes nothing. Entry rules: `colloquial` 1–4 tokens and ≤ 60 characters, `official` 1–8 tokens and ≤ 80 characters, single line, no digits or URL, tokens differ, and neither side trips `input_guardrails.screen_question` or the notice pipeline's personal-data codes. The committed glossary holds pairs seeded from the fixture review file and agent-drafted pairs for golden items `golden-039`…`golden-046` (origin `{"kind": "golden", "ref": "golden-0NN"}`), whose colloquial tokens occur in that golden question; all `proposed`.

### 7. The owner lists the pairs readably

Given the backend environment · When the owner runs `./scripts/init.sh --glossary-review` · Then each waiting pair shows its number, id, the grower's words, the official term, where it came from in plain Spanish, how many reviewed passages contain the official term, and for golden-origin pairs the golden question with the words that would be added. The full list with states goes to `build/glossary-review/pairs.txt`. It ends with `Result: N word pairs wait for your decision (A approved, R rejected). The same list is in build/glossary-review/pairs.txt.` or `Result: no word pairs wait for your decision (A approved, R rejected).`, and writes nothing under `backend/config/`.

### 8. The owner decides with one command; bad input records nothing

Given waiting pairs · When the owner runs `./scripts/init.sh --glossary-decide approve|reject "<name>" <number-or-id>…` · Then each pair gets `approved` or `rejected` with `decision: {decision, reviewed_by, reviewed_on}` (local date), the file is rewritten atomically with stable formatting, and it ends with `Result: recorded <approve|reject> for N word pairs by <name>. P still wait for your decision.` A repeated decision replaces the earlier one. Given a missing or invalid decision word or name (golden-review name rules), no pair, an unknown number or id, approval of a pair failing the entry rules, or a damaged file · Then nothing is written, it exits nonzero, and it ends with one pinned `Result:` line naming the fix. A missing backend environment ends with `Result: the glossary review did not run. Run ./scripts/init.sh --local-rag-setup.`

### 9. Check blocks a glossary that breaks reviewed cases

Given `glossary_review.py check` with explicit `--catalog --passages --cases --golden --glossary --active-campaign --as-of --k` · Then it fails (exit `1`, one line per failure, ids only) when any entry breaks the file or entry rules, or when a reviewed case or approved golden item whose state, source, passage, or critical-fact match passed without the glossary fails with it (both runs through `release_gates.evaluation_app`, BM25, extractive); the failure line names the case id and the pair ids that fired. Otherwise it exits `0` and prints counts: entries by state, cases checked, and cases improved.

### 10. Isolated, offline, and the original words stay authoritative

Tests run offline with sockets blocked. `backend/app/question_glossary.py` imports only the standard library and `app.retrieval`; no `/ask`-path module imports `question_glossary_review`, `notice_pipeline`, or `golden_set`. Release gates, `knowledge/`, and `notice_pipeline.py` are byte-unchanged.

### 11. Manual acceptance: owner walkthrough

Given validator accept · When the owner follows `Owner walkthrough: word pair review` in `docs/owner-guide/question-glossary-review.md` · Then the owner has listed the pairs, approved or rejected every one, triggered one missing-name and one unknown-number case that recorded nothing, and ended with `Result: no word pairs wait for your decision …`. The resulting glossary is committed on the feature branch, `check` is rerun and must exit `0`, and the approved/rejected counts go in the acceptance record.

## Technical approach

- `backend/app/question_glossary.py` (runtime, stdlib + `app.retrieval`): strict loader and entry rules, `QuestionGlossary.expand(question) -> str`, `identity()` digest, `load_question_glossary(environ, path)` returning the glossary or `None` plus a reason code. Fixed path `backend/config/question_glossary.json` (shipped in the container image with `backend/config/`).
- `Retriever.with_query_expansion(expand)` mirrors `with_ranker`: shares records and index, `search` applies `expand` before `_search`; each `with_*` keeps the other's setting. `ask_api` gains `get_question_glossary` (reads `app.state.question_glossary`, default `None`) and attaches expansion right after `retrieval_backend.attach`; `_answer_through_cache` appends the identity suffix to the retrieval mode passed to `model_identity` only. `release_gates.evaluation_app` never sets the state, so gates stay glossary-free.
- `create_app` gains `question_glossary=` (default: from env and path) and logs one `question_glossary` line.
- `backend/app/question_glossary_review.py` (offline): notice import, screening (`screen_question`, `notice_pipeline.personal_data_codes`), readable list, decide (reuses `golden_set.valid_name` and `write_atomically`), and the two-run check over `golden_set.approved_cases` plus reviewed cases.
- `backend/scripts/glossary_review.py`: `seed`, `list`, `decide`, `check`; raw tracebacks to `build/glossary-review/last-error.log`. `scripts/init.sh`: `--glossary-review` and `--glossary-decide` mirror the golden-review block, plus help lines. Owner-command rules: [operations constraints](../constraints/operations.md).
- File shape `question-glossary-v1`: `schema_version`, `entries[]` of `id` (`gl-NNN`), `colloquial`, `official`, `origin {kind: notice|golden, ref}`, `drafted {by, on}`, `review_state` (`proposed|approved|rejected`), `decision` (required iff not `proposed`); at most 500 entries.

## Expected file changes

- `backend/app/question_glossary.py`, `backend/app/question_glossary_review.py`, `backend/scripts/glossary_review.py` — create.
- `backend/config/question_glossary.json` — create; seeded proposals only.
- `backend/app/retrieval.py` (`with_query_expansion`), `backend/app/ask_api.py` (dependency, attach, cache identity), `backend/app/main.py` (load and log) — modify.
- `backend/tests/test_question_glossary.py` (scenarios 1–5, 10), `backend/tests/test_question_glossary_review.py` (6–9) — create; `backend/tests/fixtures/question_glossary/` — create (`notice-review.json` built from the `local_notice_pipeline` fixtures, small glossaries, a regressing pair).
- `scripts/init.sh` — modify; two owner commands and help lines.
- Docs below.

## Visual design impact

UI involved: no. Terminal output only: Spanish pair text, plain English labels like the golden review.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one line under the answer pipeline: the reviewed question glossary appends approved official terms to the retrieval query only; release gates never apply it.
- `docs/constraints/answers-and-knowledge.md`: update, "Knowledge updates and retrieval" — one MUST: query expansion uses only owner-approved glossary pairs, appends and never replaces, changes only the retrieval query, fails closed to no expansion, logs no term, and a glossary change must pass the no-regression `check`.
- `docs/owner-guide/question-glossary-review.md`: create (≤ 60 lines: list, decide, pinned `Result:` table, walkthrough); `docs/owner-guide/README.md`: one row.
- `backend/README.md`: update (≤ 30 lines: file, env switch, `seed`, `check`).
- `CONTEXT.md`: update — one glossary line for "glosario de preguntas" (approved colloquial -> official pairs).
- `docs/progress/known-limitations.md` + `PROGRESS.md` digest: update — exact token match only (no inflection or typos), a broad pair can pull unrelated passages, effect unmeasured until `colloquial_ab_evaluation`, release gates do not apply it.
- `AGENTS.md`, `DESIGN.md`, `contracts/`, `knowledge/README.md`, `docs/pilot-privacy.md`: not needed — no workflow, UI, wire, knowledge-artifact, or data-flow change.

## Focused verification (required)

<!-- verify:start -->
```sh
PY="${MANIJERO_PYTHON:-backend/.venv/bin/python}"
MANIJERO_PYTHON="$PY" ./scripts/init.sh --backend-tests -q tests/test_question_glossary.py tests/test_question_glossary_review.py tests/test_retrieval.py tests/test_hybrid_retrieval.py tests/test_answer_cache.py tests/test_ask_endpoint.py
"$PY" backend/scripts/glossary_review.py check --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json --glossary backend/config/question_glossary.json --active-campaign 2026 --as-of 2026-11-07 --k 5
```
<!-- verify:end -->

No network or model. The implementer also runs the full `./scripts/init.sh --backend-tests` once as evidence.

## Appendix

See [`question_rewriting.appendix.md`](question_rewriting.appendix.md) for research, plan, evidence, and the validator checklist.
