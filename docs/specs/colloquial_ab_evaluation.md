# Compare no rewriting, glossary rewriting, and glossary plus local-model rewriting

## Source metadata

- `id`: colloquial_ab_evaluation · `area`: evaluation · `depends_on`: question_rewriting, golden_dataset_expansion, evaluation_metrics_report (all accepted) · `status` at planning: not_started
- User-visible behavior: no app, `/ask`, `contracts/`, or copy change. An agent drafts one colloquial variant of each of the 49 approved golden questions; the owner reads them and approves or rejects each with one named command. A developer-only command then scores the approved variants three ways — no rewriting, the approved glossary, and the glossary plus the pinned local model — and writes one comparison report outside `knowledge/`. It reports the owner's adoption rule and changes no default.
- Verification: offline pytest with a fake local model and an in-process app; the integrity `check` over the repository variant set; then one real `prepare` plus `run` on the owner's Mac, re-run by the validator; commands in Focused verification.
- Owner decisions, 2026-11-10 (final, verbatim — do not reopen):
  1. "Three arms: no rewriting, glossary rewriting, glossary plus local Ollama model rewriting. Pinned local model only; no hosted model, no new spend."
  2. "Colloquial variants are drafted offline and MUST be owner-approved before any scoring; unapproved items are never read (same review discipline as the golden set)."
  3. "Adopt a mode only if hit@5 improves and no approved trap gets worse; the owner signs off at acceptance — the feature reports the rule but changes no default on its own."
  4. "Report-only, read-only over knowledge/, deterministic given the local model version; no live service."
  5. "Independent validator accept is final; no owner walkthrough."
- Planning decisions (flag to the owner if wrong): (a) "a mode" is judged against the no-rewriting control; each candidate arm is compared to arm A, and arm C versus arm B is reported as information only. (b) The model arm appends up to 4 validated official terms after the glossary terms, never replaces the grower's words — the same append-only discipline `question_rewriting` established. (c) The model is the already-pinned local drafting model in `backend/config/local_generation_model.json`; no new pin, download, or model. (d) The variant set is durable reviewed evaluation data in `backend/config/`, outside `knowledge/`; reports, review lists, and the model-term cache are under `build/colloquial-ab/` (gitignored). (e) Owner decision 5 replaces the `operations` walkthrough with the automated command walkthrough in the appendix.

## Goal

Tell the owner, from their own approved questions, whether appending approved glossary terms — and then whether also letting the pinned local model propose official terms — makes colloquial Spanish find the right reviewed passage more often without making any approved trap worse. The result is recorded evidence for a later owner decision; no default, threshold, gate, or corpus byte changes here.

## Non-goals

- Any change to `/ask`, retrieval, `ask_api`, the glossary file or its on/off default, `eval_metrics`, `golden_set`, `trap_set`, release gates, or the answer cache.
- Any default flip, config write, CI gate, threshold, exit code that depends on a metric, or quality/legal claim.
- A hosted model, a new model pin, a download, a new dependency, or spend; any live service or HTTP call to a running Manijero service.
- Writing under `knowledge/`, editing the golden/trap sets, or adding glossary pairs (that is a separate reviewed `question_rewriting` change).
- A semantic judge, faithfulness scoring, hybrid/reranker/drafting-model comparison, per-category adoption, or an owner walkthrough.
- Real grower questions, personal data, real land data, or a UI.

## Job story

When I approved everyday-word pairs and wonder whether they actually help — and whether a local model could help more — I want one comparison over colloquial versions of my own approved questions, with every score traceable to what I approved, so I can decide from evidence instead of a hunch.

## Acceptance Scenarios

### 1. One variant per approved golden item, drafted offline

Given the 49 approved golden items · When `colloquial_ab.py check` runs · Then it exits `0` only if there are exactly 49 variants, ids `coll-001`…`coll-049`, each parent `golden-0NN` approved and used once, no orphan or duplicate, every item `draft`, `approved`, or `rejected`, and `golden_sha256` matches the golden file. Each variant stores only `parent_id`, `question`, `colloquial_terms`, `drafted`, `review_state`, `decision`; expectations, land context, type, area, and segment are derived from the parent at load, so they cannot drift.

### 2. A variant is a new plain wording of the same information need

Given any approved or draft variant · When checked · Then it fails, nonzero and naming the id and rule, unless: 1–200 characters, single line, no `screen_question` hit, no digit-bearing token absent from the parent question, no URL; its tokenized text differs from the parent and from every other variant, reviewed case, and golden item. For an answered parent: `out_of_scope_topic` is `None` and 1–4 `colloquial_terms` each occur as contiguous tokens in the variant and not in the parent. For an abstained parent: if the basis is a declared omission, the same omission still matches. A `rejected` variant keeps the structural checks of scenario 1 but is exempt from these content rules, because it is never scored.

### 3. The owner lists and decides; only a decision counts

Given waiting variants · When the owner runs `./scripts/init.sh --colloquial-review` · Then each shows its number, id, parent id and question, expected outcome in plain words, the plain words it introduces, and the expected source/location; the full list with states goes to `build/colloquial-ab/variants.txt`, nothing is written under `backend/config/` except by `decide`, and it ends with `Result: N colloquial variants wait for your decision (A approved, R rejected). The same list is in build/colloquial-ab/variants.txt.` or the pinned "no … wait" form. Then `--colloquial-decide approve|reject "<name>" <number-or-id>…` records `review_state` plus `decision {decision, reviewed_by, reviewed_on}` atomically and ends with `Result: recorded <approve|reject> for N colloquial variants by <name>. P still wait for your decision.` A repeated decision replaces the earlier one; any bad input, unknown ref, damaged file, or approval of a variant that fails scenario 2 records nothing, exits nonzero, and ends with one pinned line naming the fix. The decided file is committed on the feature branch. The closed list ends `Result: no colloquial variants wait for your decision (A approved, R rejected).`; without the backend environment both commands end `Result: the colloquial variant review did not run. Run ./scripts/init.sh --local-rag-setup.`

### 4. Unapproved variants are never read

Given drafts and rejected variants · When `prepare` or `run` loads the set · Then only `approved` variants exist to it; a draft carrying a poison question never reaches the rewriter or the app (proven by a fixture). With zero approved variants either command prints one fixed `no_approved_variants` line, exits `2`, and writes nothing. The report counts approved, draft, and rejected items and never their text.

### 5. Three arms, identical except the query expansion

Given approved variants, the 49 approved golden parents, and the 26 approved traps · When `run` executes · Then one in-process app is built per arm with the same corpus, campaign, `as-of`, `k = 5`, extractive drafting, cache off, inspection on, and the same case order; the only difference is the expansion object: arm A `None`, arm B the loaded `QuestionGlossary`, arm C `QuestionGlossary` plus validated model terms. Every arm scores every case; no arm reads a different file, uses hybrid/reranker/another provider, or a live service.

### 6. The report states the rule and changes no default

Given the report · Then each candidate arm carries `hit_at_5` counts and value over the approved answered variants (the fixed denominator), its changed-query count, its trap regressions, and `adoptable` = hit@5 strictly greater than arm A **and** zero approved traps worse (`expected_state_match` or `abstention_reason_match` true→false, or `must_not_say` growth). If any variant is still `draft`, both are `not assessable (review incomplete)`; if no variant's query changed, `not adoptable (no effect)`. Arm C versus arm B is reported as information only. If both candidate arms meet the rule, the report ranks neither and the owner decides; nothing is adopted here. No file, setting, environment key, or `PROGRESS.md` default is written by the command.

### 7. Model rewrites are pinned, bounded, and fail closed

Given `prepare` · When it runs · Then it uses only the pinned local model in `backend/config/local_generation_model.json` over loopback `/api/chat` with the record's digest verified and `temperature 0`, `seed 0`; it asks only for official terms, accepts at most 4, and keeps a term only if it is 1–8 tokens, ≤ 80 characters, single line, no digit/URL, not already in the query or glossary expansion, and not screened. A screened question, an empty answer, or an invalid term yields glossary-only expansion for that case and a fixed status (`skipped_screened`, `empty`, `rejected`), otherwise `rewritten`; never a partial or invented term. A transport, digest, or pin failure stops the whole `prepare` (`model_unavailable`) and writes no cache. The cache holds ids and accepted terms only, never question text.

### 8. Deterministic, cached, and outside knowledge/

Given a completed `prepare` cache · When `run` executes twice · Then the two reports are byte-identical, `run` makes no network call, and a changed case-set digest, glossary file, model tag/digest, input file, `as-of`, campaign, or label changes `version_id` (first 16 hex of the canonical version JSON). A missing or stale cache aborts with `rewrites_missing` or `rewrites_stale` naming `prepare`; the command writes only `build/colloquial-ab/{variants.txt,rewrites/,reports/<version_id>/report.json,last-error.log}` and refuses a root inside `knowledge/` or on an input (`unsafe_output_path`).

### 9. Failures stop cleanly; metrics never choose the exit code

Given invalid inputs, an `/ask` non-200 or contract violation, an unsafe root, or an unexpected error · Then one fixed `Result:` line names the code, exit is `2`, no report is written, an earlier report is untouched, and a traceback goes only to `last-error.log`. A completed run exits `0` whatever the numbers say.

### 10. Acceptance evidence

Given the owner has decided every variant and the implementer has run `prepare` and `run` on the Mac · When the validator reruns `check`, `run`, and an independent recomputation from the report rows · Then counts, hit@5 values, trap regressions, and `version_id` match; `git diff -- knowledge/` is empty; the approved/rejected counts, the model tag and digest, the arm table, and the rule outcome are in the acceptance record. The owner's sign-off is the recorded variant decisions plus the reported rule; validator accept is final and there is no owner walkthrough.

## Technical approach

- **`backend/app/colloquial_ab.py`** (stdlib plus `app.eval_metrics`, `app.question_glossary`, `app.golden_set`, `app.trap_set`; no model import at module import): `SCHEMA_VERSION = "colloquial-ab-report-v1"`, `VARIANTS_VERSION = "colloquial-variants-v1"`, `K = 5`, `MODES = ("no_rewriting", "glossary", "glossary_plus_model")`, the strict `load_variants`/`variant_failures`/`check_variants` rules, `approved_cases`, readable rendering, `decide`, `GlossaryPlusModel(glossary, terms_by_id)` (exposes `expand`, appends, dedupes, ≤ 4 model terms and ≤ 8 total), `term_failures`, `prepare_rewrites`, `rewrite_cache_key`, `run_arms`, `trap_worse`, `adoption`, `version_block`, `version_id`, `build_report`, `result_line`, `abort_line`, canonical atomic write, `check_output_root`.
- Variants bind to the golden file by `golden_sha256`; expectations come from the approved parent at load and are converted to `pac-answer-eval-v2` cases with the variant id, so a changed parent is re-read, never copied. Report rows are `eval_metrics.canonical_row` plus `parent_id`, `glossary_pairs` (approved pair ids that fired), `model_terms`, and `model_status`; they never hold question, answer, passage, or land text.
- Reuse `eval_metrics.metric_block`/`case_row` for hit@k and rows, `question_glossary.load_question_glossary({SETTING_ENV: "on"}, DEFAULT_PATH)` for arm B, `local_generation.load_local_model_record` + `evaluate_local_model_record` + `OllamaTransport` (own JSON `format` schema) for `prepare`, and `eval_metrics.check_reports_root` semantics for the output root. Tests inject a fake rewriter and fake transports.
- **`run`**: one `create_app(load_config({MANIJERO_ACTIVE_CAMPAIGN: campaign}), retention_store=None, answer_cache=None, answer_inspection=True, question_glossary=<arm object>)` per arm with the same dependency overrides as `evaluate_metrics`; `answer_eval.evaluate` over the same tagged case list (`colloquial`, `golden`, `trap`); env isolated like `evaluate_metrics._isolated_environment` plus the glossary key. Arm A passes `None`.
- **`backend/scripts/colloquial_ab.py`**: `list` (owner), `decide` (owner), `check` (developer/validator: explicit `--catalog --passages --cases --golden --traps --variants`, exit 0/1, ids only), `prepare` (developer, needs the pinned loopback model), `run` (offline over the cache). `main(argv, *, reports_root=None, rewriter=None, today=None)`.
- **`scripts/init.sh`**: `--colloquial-review` and `--colloquial-decide` mirror the `--glossary-review` block (backend venv or `python-env.sh dev --if-present`, before the `local.properties` write), plus help lines. No `--colloquial-run`: `prepare`/`run` are developer commands with explicit paths.
- Fixed abort codes: `invalid_inputs`, `no_approved_variants`, `rewrites_missing`, `rewrites_stale`, `model_unavailable`, `ask_failed`, `unsafe_output_path`, `internal_error`. `Result:` shape: `Result: compared 3 ways on N approved colloquial variants (M answered, C with a changed query) and T approved traps: hit@5 no rewriting a/M, glossary b/M, glossary+model c/M; model rewrites: R rewritten, E empty, X rejected, S skipped; traps worse: glossary y, glossary+model z; verdict: glossary <…>, glossary+model <…>. No setting was changed. Report only, no gate. Report: <path>.`

## Expected file changes

- `backend/app/colloquial_ab.py`, `backend/scripts/colloquial_ab.py` — create.
- `backend/config/colloquial_variants.json` — create; 49 agent-drafted variants, all `draft` until the owner decides.
- `backend/tests/test_colloquial_ab.py`, `backend/tests/test_colloquial_ab_command.py`, `backend/tests/fixtures/colloquial_ab/` — create.
- `scripts/init.sh` — modify; two owner flags and help lines.
- `docs/owner-guide/colloquial-variants-review.md` (create, ≤ 60 lines), `docs/owner-guide/README.md` (one row).
- Docs listed under Durable documentation impact.
- Do not change: `knowledge/`, `backend/config/question_glossary.json`, `ask_api`, `retrieval`, `eval_metrics`, `golden_set`, `trap_set`, `contracts/`, `shared/`, requirements.

## Visual design impact

UI involved: no. Terminal output only; Spanish question text and English labels like the other review commands.

## Durable documentation impact

- `ARCHITECTURE.md`: update — one bullet after `eval_metrics.py`: the colloquial A/B command scores the same approved cases through the in-process `/ask` three times, differing only in query expansion, and is report-only.
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation": update — one MUST: the comparison reads only owner-approved variants, differs only in the query expansion, writes outside `knowledge/`, uses only the pinned local model, reports the adoption rule, and changes no default.
- `docs/risks-and-open-questions.md`: update — one line: variants are agent-drafted from the same material the glossary was seeded from, sets are small, BM25 extractive only, one local model on one Mac, and nothing was adopted.
- `docs/progress/known-limitations.md` + `PROGRESS.md` digest: update the glossary line — measured on N approved colloquial variants with the named local model; no adoption.
- `backend/README.md`: update (≤ 30 lines: commands, artifact paths, rule, report-only).
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `knowledge/README.md`, `contracts/`: not needed — no workflow, term, UI, knowledge artifact, or wire change.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests -q tests/test_colloquial_ab.py tests/test_colloquial_ab_command.py tests/test_question_glossary.py tests/test_eval_metrics.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/colloquial_ab.py check --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --golden knowledge/golden_set.json --traps knowledge/trap_set.json --variants backend/config/colloquial_variants.json
git diff --quiet -- knowledge/
```
<!-- verify:end -->

No network, no model, no running service. `prepare` and the real `run` are evidence steps, run once on the owner's Mac with the pinned model.

## Appendix

See [`colloquial_ab_evaluation.appendix.md`](colloquial_ab_evaluation.appendix.md) for repository research, the implementation plan, the verification plan, evidence to capture, and the validator checklist.
