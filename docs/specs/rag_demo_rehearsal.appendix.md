# rag_demo_rehearsal — appendix

## Repository research

### Files inspected

- `scripts/init.sh` — early owner-command dispatch (before `local.properties`), `usage`, and `--check` listing; `--local-smoke` is the closest pattern.
- `backend/scripts/local_rag.py` — owner service commands and the `smoke` dispatch; the rehearsal needs no new `local_rag.py` command.
- `backend/app/local_rag_service.py` — `--local-rag-start` states `MANIJERO_DEPLOYMENT_PROFILE=development`, so `/ask` carries `inspection`; the run record and port env live here.
- `backend/app/ask_api.py` — closed `AskRequest` (`question`, `land_context`, `retain_for_improvement`) and `AskResponse` (`status`, `answer`, `sources`, `land_scope`, `land_ids_to_choose`, `inspection`).
- `backend/app/main.py` — `/health` returns `{"status":"ok","service":"manijero-backend"}`; `/ready` returns `{"status":"ready"|"unavailable","service":...}` with 200/503.
- `backend/app/abstention.py` — `ABSTENTION_REASONS` fixed codes; the response exposes them only through `inspection.outcome`.
- `backend/app/review_package.py` — `prepare`, `record_decision`, `merge`, `ReviewPackageError` codes, and the approval/digest/drift gates.
- `backend/scripts/knowledge_review.py` — the same three operations as a CLI; the rehearsal calls the module directly to keep failures typed.
- `backend/tests/test_knowledge_update_review.py` — the synthetic proposal shape, `SUCCESS_ID`, and the `prepare`→`merge` sequence reused here.
- `backend/tests/fixtures/change_impact/` — ingestion state, quarantine files, catalog, passages, and cases; the only demo inputs for the update step.
- `knowledge/pac_coverage.md` — three approved topics, the known abstaining subsidy case, and the absence of `applicability` (no land clarification).
- `knowledge/pac_answer_eval.json` — fixed questions with recorded outcomes used to choose the two rehearsal questions.
- `contracts/openapi.yaml` — `AskResponse` fields and the development-only `inspection` schema.
- `docs/specs/local_end_to_end_smoke.md` — owner-command shape: PASS/FAIL lines, one `Result:`, fixed question, no text in output.
- `docs/specs/rag_inspector_view.md` — the inspector is manual, local-test-build, loopback, and `development` only.
- `shared/src/commonMain/composeResources/values/strings.xml` and `chat/ChatTranscript.kt` — pinned scope captions and `Sin respuesta segura`.
- `docs/owner-guide.md` — English operator-guide style: numbered steps, expected `Result:`, "If the result differs" table.
- `docs/constraints/operations.md` — one named command, plain `Result:`, prerequisite checks, documented walkthrough.
- `PROGRESS.md` — current state, verification tiers, and the known-limitations index.

### Existing patterns to follow

- Owner commands are added to the early `scripts/init.sh` dispatch, print one final `Result:` line, and never require the owner to type a module path.
- Checks run offline in pytest with a temporary `MANIJERO_LOCAL_HOME` and a free `MANIJERO_LOCAL_RAG_PORT`; no real service is started.
- Fixed, non-personal questions keep the demo deterministic; output carries outcome codes and counts, never question/answer/passage text.
- The review package is deterministic: fixed `as_of`, sorted canonical JSON, no wall-clock timestamp.
- `review_package.prepare` is read-only over `knowledge/`; only `merge` writes, and only into the paths passed to it.

### Current gaps

- No rehearsal command, demo script, or owner section exists.
- The approved corpus declares no `applicability`, so a real `/ask` never returns `needs_land_clarification`; the feature title's clarification can only be explained (or shown with the mock service), not rehearsed against the real service.
- `--backend` (plain Uvicorn) may not set `MANIJERO_DEPLOYMENT_PROFILE=development`, so `inspection` may be absent; the rehearsal must pass on the public response fields alone.
- The real live run needs the owner's Mac, the local stack, and an app surface; it is not reproducible in CI.

## Implementation plan

1. Add `backend/scripts/demo_rehearsal.py`: `main()` with `--url` and fixed constants; `run()` returns 0/1; a `Step` result list; one `Result:` line.
2. Implement service steps with `urllib.request`: `GET /health`, `GET /ready`, then two `POST /ask` calls with `land_context {mode: "general", lands: []}` and `retain_for_improvement: false`; classify each into PASS/FAIL/SKIP.
3. Implement the review step: temporary copy of `backend/tests/fixtures/change_impact`, write the synthetic proposal, `prepare` → assert `ready_for_review`, unapproved `merge` → expect `approval_required`, `record_decision` approve, `merge` with cases → assert ids; compare canonical `knowledge/` hashes around it. Remove the temp dir in `finally`.
4. Add `--demo-rehearsal` to `scripts/init.sh` early dispatch with the one-argument check, venv resolution, setup pair, and `exec`; add it to `usage` and the `--check` listing.
5. Add `backend/tests/test_demo_rehearsal.py`: fake threaded HTTP service (pass, trap answered, malformed/503), closed port (SKIP path, review still runs), canonical hashes, request body safety, `init.sh` misuse/dispatch.
6. Write `docs/demo-script.md` in plain Spanish: preparation, rehearsal, live order, manual steps, synthetic explanation, fallback, closing limits.
7. Update `docs/owner-guide.md` (section + expected lines + failure table + pointer), `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`.
8. Run the focused block; record the result. Run the live command if the stack exists; otherwise record exactly which steps were not run.
9. At acceptance, update `PROGRESS.md` ("Start and verify" line plus the limitations index), `docs/progress/known-limitations.md`, and one line in `docs/progress/session-log.md`.

### Fixed rehearsal values

- Service URL: `http://127.0.0.1:${MANIJERO_LOCAL_RAG_PORT:-8000}`; `--url` overrides for tests only.
- Grounded question: `¿Cuál es la fecha final para presentar la solicitud única de 2026?` (recorded correct 2/2).
- Trap question: `¿Qué importe de ayuda me corresponde por hectárea?` (recorded abstained).
- Review fixtures: `backend/tests/fixtures/change_impact`; `SUCCESS_ID = 7825dfd2af88508fc05c2e393052def95604929145ccd2f2771f71bb30936814`; `AS_OF = 2099-10-27`.
- Reviewer `Revisora de ensayo`; author `preparador-sintetico`; new source `fixture-rd-2200-2099`; new passage `fixture-pasaje-rd-2200-art-1`; passage text `Texto sintético de revisión; no afirma ningún plazo real.`
- Proposal fields mirror `test_knowledge_update_review.py` (`source_entry`, `passage_entry`, `links`, `unresolved_questions`), declared synthetic in the summary.
- Expected output labels: `PASS  Service: /health and /ready answer`, `PASS  Grounded answer: <n> approved sources, land_scope general`, `PASS  Trap abstention: no sources`, `PASS  Reviewed update: draft blocked, human approval, temporary merge (synthetic)`, and the matching `FAIL`/`SKIP` forms.
- Result lines: `Result: the demo rehearsal passed (4 of 4 steps)...` or `Result: the demo rehearsal is incomplete (N skipped)... Start it with ./scripts/init.sh --local-rag-start, then run this command again.`

## Verification plan

- `bash -n scripts/init.sh` — exit 0.
- `tests/test_demo_rehearsal.py -q` — all pass; loopback-only fake service and a closed port; no real stack.
- `./scripts/init.sh --demo-rehearsal` after `--local-rag-start` — four `PASS` lines plus the passing `Result:`; record the outcome codes, not the text.
- `docs/demo-script.md` manual walkthrough — record which app steps were watched; if the inspector is absent, record the `--backend`/non-development fallback.
- E2E: the rehearsal command is the end-to-end service check for this feature; no UI automation is added (owner decision 1). The UI steps stay a named owner walkthrough.
- E2E evidence limits: a pass proves reachability, grounding-with-sources, abstention, and the review gate for the fixed inputs; it proves no answer quality, legal coverage, or general accuracy.

## Evidence to capture

- Focused block result (one line) and the test names covering each behavior.
- Live run: exit code and the fixed step outcomes; explicitly list any step not run and why.
- Canonical hash check: `knowledge/source_catalog.json` and `knowledge/passages.json` unchanged.
- Manual app steps actually watched (scope caption, `Inspeccionar`, trap card) or "not run".
- Any deviation from the fixed labels/Result lines, with the reason.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

### 2026-11-06 — implementer

- `bash -n scripts/init.sh` — exit 0.
- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature rag_demo_rehearsal` — focused tier passed; 11 passed (the block ran unchanged through `--feature`).
- `CI=true ./scripts/init.sh --fast` — all 10 offline checks passed (backend suite: 1882 passed, 4 skipped).
- Tests (`tests/test_demo_rehearsal.py`, 11): `test_rehearsal_passes_and_sends_general_non_retained_requests`, `test_public_fields_pass_when_the_development_inspection_is_absent`, `test_trap_answered_fails_only_that_step_and_the_rest_still_runs`, `test_malformed_grounded_reply_fails_that_step`, `test_unapproved_source_address_fails_the_grounded_step`, `test_unknown_abstention_code_fails_the_trap_step`, `test_closed_port_skips_service_steps_and_still_runs_the_reviewed_update`, `test_synthetic_proposal_is_declared_and_uses_the_fixed_values`, `test_reviewed_update_blocks_the_draft_and_leaves_canonical_knowledge_unchanged`, `test_init_script_runs_the_rehearsal_against_the_configured_port`, `test_init_script_refuses_an_extra_argument_without_a_request_or_a_write`.
- Canonical hash: `knowledge/source_catalog.json` and `knowledge/passages.json` byte-identical before/after every rehearsal run (in-process check in the review step and in the subprocess tests).
- Live/manual **not run**: `./scripts/init.sh --demo-rehearsal` with the real `--local-rag-start` stack, and the manual app steps (scope caption, `Sin respuesta segura`, `Inspeccionar`). No local stack, Ollama, emulator, or owner Mac is available here; the live run is the owner walkthrough in `docs/owner-guide.md` / `docs/demo-script.md`.
- Deviations from the fixed labels/Result lines: none. `docs/progress/known-limitations.md` and `docs/progress/session-log.md` lines are left for acceptance.

### 2026-11-06 — orchestrator live run

- `./scripts/init.sh --local-rag-start` — started the hybrid service on release `3050d1b8b5e10f82` with local drafting at `http://127.0.0.1:8000`.
- `./scripts/init.sh --demo-rehearsal` — exit 0, twice in a row: 4 `PASS` lines (service, grounded answer with 1 approved source and `land_scope general`, trap abstention, reviewed synthetic update) and the passing `Result:` line; `git status --short knowledge/` empty after both runs.
- `./scripts/init.sh --local-rag-stop` — service stopped; the Mac is back to its prior state.
- `./scripts/init.sh --demo-rehearsal` with the service stopped — exit 1; the three service steps printed `SKIP`, the reviewed-update step still `PASS`, and the `Result:` line named `--local-rag-start` (scenario 3 live).
- Not observed: the app-only demo steps (source cards with the pinned scope caption, `Sin respuesta segura`, `Inspeccionar`) — no one watched a GUI. They remain the owner walkthrough in `docs/owner-guide.md`.

## Handoff

- Status: `passing`; validator accepted with the condition "pending owner walkthrough".
- Done and uncommitted before the hold commit: the whole feature (command, tests, Spanish script, owner guide, boundary docs, validator record).
- Live service-level rehearsal ran here and passed twice; app-only steps not watched.
- Next: owner runs `docs/demo-script.md` and reports whether every step matched; then acceptance is an evidence-only update (no second validator).
- Last checks: focused 11 passed; `--fast` all 10 checks passed; live `--demo-rehearsal` exit 0.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected; no service, contract, knowledge, app, or dependency change.
- [ ] Four steps and their PASS/FAIL/SKIP rules match scenarios 1–3; exactly one `Result:` line; exit 0/1/2.
- [ ] The unapproved merge is refused; the approved merge writes only the temporary fixture copies; canonical `knowledge/` hashes unchanged.
- [ ] Output, logs, and artifacts carry no question, answer, passage, land, or token text; requests use `general` with no lands and no retention.
- [ ] Service-unavailable path still runs the review step and states exactly which steps were skipped.
- [ ] `docs/demo-script.md` is plain Spanish, marks manual steps, declares synthetic content, and makes no legal/coverage/quality claim beyond `knowledge/pac_coverage.md`.
- [ ] `docs/owner-guide.md` expected lines match the implementation; failure table names real outputs.
- [ ] Durable documentation impact followed; no fact restated across files.
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature rag_demo_rehearsal`.
- [ ] `feature_list.json`, `PROGRESS.md`, known limitations, session log, and the validation record are updated at acceptance.
