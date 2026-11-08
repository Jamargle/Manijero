# question_rewriting — appendix

Contract: [`question_rewriting.md`](question_rewriting.md).

## Repository research

Inspected (2026-11-08, planner):

- `backend/app/ask_api.py` — `ask_question` screens the original question, then `_answer` runs the year check, `_prepare_runtime_corpus`, `retrieval_backend.attach`, then `answer_with_clarification` or `_answer_through_cache`; the expansion attach point is right after `attach`.
- `backend/app/clarification.py`, `backend/app/abstention.py`, `backend/app/generation.py:1060` — the three `corpus.search(question, k)` call sites; `scope_abstention` and `has_unsupported_presupposition` use the question text directly, so wrapping `search` keeps them on the original words.
- `backend/app/retrieval.py` — `tokenize` (NFKD, accent strip, `[a-z0-9]+`, Spanish stopwords), `Retriever.with_ranker` (pattern for `with_query_expansion`), `search`/`_search` (lexical gate, ranker gets the question string).
- `backend/app/answer_cache.py` — `model_identity(model_version, retrieval_mode, k, max_claims)` and `cache_key`; the glossary digest rides in the retrieval-mode field.
- `backend/app/main.py` — `create_app` keyword-injection pattern and one operational log line per startup setting (cache, inspection, provider).
- `backend/app/release_gates.py` — `evaluation_app` builds a pinned app without `create_app` and without `app.state` extras; reused by `check` for both runs.
- `backend/app/answer_eval.py` — `evaluate(cases, client, catalog, passages, k, coverage=)` rows carry `expected_state_match`, `source_match`, `passage_match`, `critical_facts_match`.
- `backend/scripts/evaluate_pac_answers.py` — uses the module-level `app.main.app`, so it will apply approved pairs once any exist (intended: it reflects the served path).
- `backend/app/input_guardrails.py` — `screen_question`, `contains_personal_identifier`.
- `backend/app/notice_pipeline.py` — `notice-review-v1` (`vocabulary[]` of `colloquial`, `standard`, `sources`), `personal_data_codes`, `fold`; must not be imported on the `/ask` path (its constraint).
- `backend/tests/fixtures/local_notice_pipeline/` — three invented notices and `fake_model_outputs.json` (7 distinct pairs, e.g. `los papeles` -> `documentación de la solicitud`).
- `backend/app/golden_set.py` — `valid_name`, `write_atomically`, `dump_document`, `approved_cases`, `resolve_refs`, `record_decision` (decide pattern to mirror).
- `knowledge/golden_set.json` — colloquial items `golden-039`…`golden-046`; `knowledge/passages.json` — 7 reviewed passages (the vocabulary the official terms should hit).
- `scripts/init.sh:342-359` — `--golden-review`/`--golden-decide` dispatch block to mirror.
- `backend/container/Dockerfile*` — `backend/config/` is copied into the image, so the glossary ships with the service; `knowledge/` is not.
- `docs/specs/golden_dataset_expansion.md`, `docs/specs/local_notice_pipeline.md` — owner-review and notice-pipeline contracts reused.

Not inspected: `test_ask_endpoint.py` internals (assumed to build apps with `create_app` overrides), `answer_inspection.py` (unchanged).

## Implementation plan

1. `question_glossary.py`: entry rules, loader (size cap, schema, ids unique, approved pairs unique by token sequences), `expand`, `identity`, env parse; reason codes `missing`, `unreadable`, `too_large`, `wrong_schema`, `invalid_entry`, `disabled`, `invalid_setting`.
2. `Retriever.with_query_expansion`; make `with_ranker` keep the expander and vice versa.
3. `main.create_app(question_glossary=...)` + log line; `ask_api.get_question_glossary`, attach after `retrieval_backend.attach`, cache identity suffix.
4. `question_glossary_review.py`: screening (adds `screen_question` + `personal_data_codes` to the runtime rules), `seed`, readable `render_list` (passage counts via `tokenize` over `knowledge/passages.json`; golden expansion preview), `decide`, `check`.
5. `backend/scripts/glossary_review.py` CLI, exit codes `0/1/2`, `last-error.log`; `scripts/init.sh` blocks and help lines.
6. Fixture `backend/tests/fixtures/question_glossary/notice-review.json`: build it with the `notice_pipeline` writer over the `local_notice_pipeline` fixtures and fake outputs; a test rebuilds it and asserts byte equality.
7. Seed `backend/config/question_glossary.json`: run `seed` on that fixture; then draft golden-origin pairs (candidates below), all `proposed`, `drafted.by: agent:question_rewriting`.
8. Run `check` on the committed file (zero approved -> passes trivially); then temporarily approve all pairs in a scratch copy and record which would regress (evidence only, never committed).
9. Tests, then docs (contract list), then the focused block and the full backend suite.

Golden-origin candidates (implementer verifies each against the rules; owner decides): `mandar` -> `presentar` (039), `tocar` -> `modificar` (040), `papeleo` -> `solicitud` (041), `avisar` -> `notificaciones` (044), `internet` -> `medios electrónicos` (044, 046), `equivocado` -> `error material` (045), `arreglar` -> `rectificar` (045), `ordenador` -> `medios electrónicos` (046). Skip over-broad words (`ir`, `hacer`). Exact-token matching means `mandar` does not fire on `mandado`/`manden` (040, 044); record this, do not add inflections.

## Tests (by behavior)

- `test_question_glossary.py`: append-only and original-first; only approved; longest/non-overlapping; whole-token; already-present skip; cap 4; idempotent; hybrid ranker receives expanded query; each fail-closed reason and the log line has no term; cache identity suffix on/off; screen/scope/presupposition/drafting payload/trace/retention see the original (spy retriever and generator); zero approved byte-identical responses; `/ready` unaffected; import isolation (AST scan).
- `test_question_glossary_review.py`: seed adds/skips/idempotent/damaged file; personal-data, injection, digit, URL pairs refused on seed and approve; list text and `Result:` lines; decide records, replaces, atomic, every bad input writes nothing; `check` passes on the committed file and fails with case and pair ids on a regressing fixture pair; fixture `notice-review.json` rebuild equality; committed golden-origin colloquials occur in their questions.

## Verification plan

- The focused block in the contract (targeted pytest + `check` on canonical files).
- Full `./scripts/init.sh --backend-tests` once.
- Manual: `./scripts/init.sh --glossary-review` on the committed file, then a scratch-copy decide (never the committed file before the owner walkthrough).
- Owner walkthrough after validator accept (contract scenario 11).

## Evidence to capture

- Command lines and one-line results for the focused block, full suite, and `check`.
- Seed counts (added, skipped) and the entry ids with origin per pair.
- Scratch all-approved `check` result: regressions and improvements by case id.
- `Result:` lines from list and one bad-input decide.

## Risks

- `personal_data_codes` may flag capitalised official terms (for example "Sistema de Gestión de Ayudas") as names; prefer lowercase official terms and record any refusal.
- Broad single-token pairs (`mandar`, `papeleo`) can pull unrelated passages; `check` catches regressions only on reviewed cases.
- Owner approvals happen after validator accept; `check` must be rerun on the approved file before merge.

## Handoff

Status `passing`; validator returned accept with condition `pending owner walkthrough` (2026-11-08, `docs/validations/question_rewriting.md`), held in commit `chore: hold question_rewriting at passing pending owner walkthrough`. Next: owner walkthrough, then an evidence-only update sets `accepted` (no second validator). Left for the owner walkthrough (contract scenario 11): approve or reject the 15 `proposed` pairs, rerun `check` on the result, and commit the glossary. Noted for the validator: `mandar` does not fire on `mandado`/`manden` (exact tokens, by design); `--glossary-review` counts only contiguous official-term matches in passages, so most notice pairs show 0.

## Feature evidence

Implementer, 2026-11-08 (status `passing`, not accepted; owner walkthrough pending):

- `./scripts/init.sh --feature question_rewriting`: 278 passed (focused pytest) and `glossary check: 15 entries OK (proposed=15, approved=0, rejected=0); 66 cases checked, 0 improved`.
- `./scripts/init.sh --backend-tests`: 3021 passed, 9 skipped. `./scripts/init.sh --fast`: all 10 offline checks passed.
- Seed from the fixture `notice-review.json`: added 7, 0 skipped (`gl-001`..`gl-007`, origin `notice`). Golden-origin proposals, all added: `gl-008` mandar->presentar (039), `gl-009` tocar->modificar (040), `gl-010` papeleo->solicitud (041), `gl-011` avisar->notificaciones (044), `gl-012` internet->medios electrónicos (044), `gl-013` equivocado->error material (045), `gl-014` arreglar->rectificar (045), `gl-015` ordenador->medios electrónicos (046). No candidate was refused by the rules; `golden-042` (`ir`) and `golden-043` skipped on purpose.
- Scratch all-approved copy (never committed): `check` exit 0, `15 entries OK (approved=15); 66 cases checked, 3 improved`, no regression.
- Regressing fixture `tests/fixtures/question_glossary/regressing.json` (`obligatorio` -> passage wording): `check` exit 1, `cuaderno-digital-obligatorio: breaks with the glossary; pairs fired: gl-001`.
- Owner commands through `init.sh`: `--glossary-review` ends `Result: 15 word pairs wait for your decision (0 approved, 0 rejected). ...`; empty-name decide and unknown number `99` each end with a pinned `Result: nothing was recorded. ...` line and change nothing.
- Changed an existing test: `test_notice_pipeline.py::test_only_the_cli_and_tests_reference_the_notice_pipeline` now also allows `question_glossary_review.py` (the offline review tool reads `notice-review-v1` and reuses `personal_data_codes`); `test_question_glossary.py` asserts nothing on the `/ask` path imports it.

## Validator checklist

- [ ] Search receives `<original> <official…>`; nothing else sees the expanded text (spy tests present and passing).
- [ ] Only `approved` pairs apply; zero approved is byte-identical behavior and cache identity.
- [ ] Matching rules (whole-token, longest, non-overlapping, skip present, cap 4, idempotent) tested.
- [ ] Every fail-closed path disables expansion without breaking `/ask` or `/ready`; log line carries no term.
- [ ] Cache identity includes the glossary digest only when expansion is on.
- [ ] `seed` never changes existing entries; refused pairs are counted, not echoed.
- [ ] Owner commands: list and decide output, pinned `Result:` lines, bad input writes nothing.
- [ ] `check` fails on a regressing pair and passes on the committed file.
- [ ] `question_glossary.py` imports only stdlib + `app.retrieval`; release gates, `knowledge/`, `notice_pipeline.py`, `contracts/` unchanged.
- [ ] Committed glossary entries are all `proposed` until the owner walkthrough; golden-origin colloquials occur in their questions.
- [ ] Docs per contract; owner guide ≤ 60 lines, backend README ≤ 30 lines.
- [ ] Focused block runs unchanged via `./scripts/init.sh --feature question_rewriting`.
