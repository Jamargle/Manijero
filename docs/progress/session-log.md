# Session log

Chronological pointer index for Manijero, newest entries last. This file records **what happened
and where the record lives**, never the verification itself: an accepted feature's raw verification
is the `Feature evidence` section of the feature's appendix (`docs/specs/<feature-id>.appendix.md`), and its authoritative
acceptance record is `docs/validations/<feature-id>.md`. Add exactly one line per event and do not
restate evidence here.

| Date | Event | Record |
|---|---|---|
| 2026-10-05 | Build brief initiated from the user's olive-grove-manager description. | `docs/build-brief.md` |
| 2026-10-05 | Discovery documents created. | `CONTEXT.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md` |
| 2026-10-07 | Harness starter created, then completed. | `AGENTS.md`, `scripts/init.sh`, `feature_list.json` |
| 2026-10-08 | Startup harness refreshed; MVP work split into session-sized features. | `AGENTS.md`, `feature_list.json` |
| 2026-10-09 | Product discovery and harness pass; conflicts resolved, extra skills added. | `docs/`, `.agents/skills/` |
| 2026-10-11 | Subagent workflow agents added. | `.opencode/agents/` |
| 2026-10-11 | `backend_health` accepted. | `docs/specs/backend_health.md` · `docs/validations/backend_health.md` |
| 2026-10-11 | `chat_home` completed (acceptance record reconstructed 2026-10-13). | `docs/specs/chat_home.md` · `docs/validations/chat_home.md` |
| 2026-10-11 | `answer_api_contract` accepted. | `docs/specs/answer_api_contract.md` · `docs/validations/answer_api_contract.md` |
| 2026-10-11 | `local_land_store` accepted. | `docs/specs/local_land_store.md` · `docs/validations/local_land_store.md` |
| 2026-10-12 | `add_land` accepted. | `docs/specs/add_land.md` · `docs/validations/add_land.md` |
| 2026-10-12 | `suggested_questions` accepted. | `docs/specs/suggested_questions.md` · `docs/validations/suggested_questions.md` |
| 2026-10-12 | `source_catalog_validation` accepted. | `docs/specs/source_catalog_validation.md` · `docs/validations/source_catalog_validation.md` |
| 2026-10-12 | `chat_question_submission` accepted. | `docs/specs/chat_question_submission.md` · `docs/validations/chat_question_submission.md` |
| 2026-10-13 | `visual_foundation` added as a feature definition and wired as a dependency of the themed features. | `feature_list.json` |
| 2026-10-13 | Documentation consistency pass over accepted features (reconstructed `chat_home` record, linked validation records). | `docs/validations/` |
| 2026-10-13 | `visual_foundation` accepted. | `docs/specs/visual_foundation.md` · `docs/validations/visual_foundation.md` |
| 2026-10-13 | `source_retrieval` accepted. | `docs/specs/source_retrieval.md` · `docs/validations/source_retrieval.md` |
| 2026-10-13 | `grounded_answer_generation` accepted. | `docs/specs/grounded_answer_generation.md` · `docs/validations/grounded_answer_generation.md` |
| 2026-10-13 | `land_list` accepted. | `docs/specs/land_list.md` · `docs/validations/land_list.md` |
| 2026-10-13 | `safe_abstention` accepted. | `docs/specs/safe_abstention.md` · `docs/validations/safe_abstention.md` |
| 2026-10-13 | `network_error_recovery` accepted. | `docs/specs/network_error_recovery.md` · `docs/validations/network_error_recovery.md` |
| 2026-10-13 | `edit_land` accepted. | `docs/specs/edit_land.md` · `docs/validations/edit_land.md` |
| 2026-10-13 | `response_states` accepted. | `docs/specs/response_states.md` · `docs/validations/response_states.md` |
| 2026-10-13 | `remove_land` accepted. | `docs/specs/remove_land.md` · `docs/validations/remove_land.md` |
| 2026-10-13 | `answer_source_cards` accepted. | `docs/specs/answer_source_cards.md` · `docs/validations/answer_source_cards.md` |
| 2026-10-13 | `minimal_land_context` accepted. | `docs/specs/minimal_land_context.md` · `docs/validations/minimal_land_context.md` |
| 2026-10-13 | `land_clarification` accepted. | `docs/specs/land_clarification.md` · `docs/validations/land_clarification.md` |
| 2026-10-13 | `answer_land_scope` accepted. | `docs/specs/answer_land_scope.md` · `docs/validations/answer_land_scope.md` |
| 2026-10-13 | `land_data_disclosure` accepted. | `docs/specs/land_data_disclosure.md` · `docs/validations/land_data_disclosure.md` |
| 2026-10-13 | `chat_accessibility` accepted. | `docs/specs/chat_accessibility.md` · `docs/validations/chat_accessibility.md` |
| 2026-10-13 | `land_form_accessibility` accepted. | `docs/specs/land_form_accessibility.md` · `docs/validations/land_form_accessibility.md` |
| 2026-10-13 | `land_safety_evaluation` accepted. | `docs/specs/land_safety_evaluation.md` · `docs/validations/land_safety_evaluation.md` |
| 2026-10-16 | `android_mvp_build` accepted. | `docs/specs/android_mvp_build.md` · `docs/validations/android_mvp_build.md` |
| 2026-10-16 | `desktop_mvp_build` accepted. | `docs/specs/desktop_mvp_build.md` · `docs/validations/desktop_mvp_build.md` |
| 2026-10-17 | Harness: split `PROGRESS.md` into a status board plus on-demand detail. | `PROGRESS.md`, `docs/progress/current-state.md` |
| 2026-10-17 | Harness: reduced `feature_list.json` to a lean index and moved its evidence into each spec's "Feature evidence" section. | `feature_list.json`, `docs/specs/<feature-id>.md` |
| 2026-10-17 | Harness: split verification into tiers (`--fast`/`--feature`/`--backend-tests`) and put the backend in the gate. | `scripts/init.sh` |
| 2026-10-17 | Harness: split the CI gate by change type and cached pip. | `.github/workflows/gate.yml` |
| 2026-10-17 | Harness: moved the session log out of `PROGRESS.md`. | `docs/progress/session-log.md` |
| 2026-10-17 | Harness: collapsed the four overlapping copies of feature evidence. | deleted `docs/progress/feature-evidence.md`; this log is now a one-line pointer index; canonical stores are `docs/validations/<feature-id>.md` (acceptance) and the spec's "Feature evidence" (raw verification) |
| 2026-10-17 | Harness: made `feature_list.json` a true lean index — moved each feature's user-visible behavior, verification, and notes into its spec's "Source metadata" section; the index now carries only `id`, `area`, `title`, `status`, `depends_on`, `spec`, and `validation`. | `feature_list.json`, `docs/specs/<feature-id>.md` |
| 2026-10-17 | Harness: split every accepted spec into a bounded contract (`docs/specs/<id>.md`) plus a verbatim appendix (`docs/specs/<id>.appendix.md`) holding repository research, implementation plan, verification plan, validator checklist, and "Feature evidence"; evidence now records to the appendix. | `docs/specs/`, `feature_list.json`, `AGENTS.md`, `PROGRESS.md`, `.agents/skills/feature-{spec,implementer,flow,validator}/` |
