# Session log

Chronological pointer index for Manijero, newest entries last. This file records **what happened
and where the record lives**, never the verification itself: an accepted feature's raw verification
is the `Feature evidence` section of the feature's appendix (`docs/specs/<feature-id>.appendix.md`), and its authoritative
acceptance record is `docs/validations/<feature-id>.md`. Add exactly one line per event and do not
restate evidence here.

| Date | Event | Record |
|---|---|---|
| 2026-10-05 | Build brief initiated from the user's olive-grove-manager description. | `docs/archive/build-brief.md` |
| 2026-10-05 | Discovery documents created. | `CONTEXT.md`, `docs/domain-model.md`, `docs/risks-and-open-questions.md` |
| 2026-10-07 | Harness starter created, then completed. | `AGENTS.md`, `scripts/init.sh`, `feature_list.json` |
| 2026-10-08 | Startup harness refreshed; MVP work split into session-sized features. | `AGENTS.md`, `feature_list.json` |
| 2026-10-09 | Product discovery and harness pass; conflicts resolved, extra skills added. | `docs/`, `.agents/skills/` |
| 2026-10-11 | Subagent workflow agents added. | `.opencode/agents/` |
| 2026-10-11 | `backend_health` accepted. | [backend_health.md](../specs/backend_health.md) · [acceptance](../validations/backend_health.md) |
| 2026-10-11 | `chat_home` completed; acceptance record reconstructed 2026-10-13. | [chat_home.md](../specs/chat_home.md) · [acceptance](../validations/chat_home.md) |
| 2026-10-11 | `answer_api_contract` accepted. | [answer_api_contract.md](../specs/answer_api_contract.md) · [acceptance](../validations/answer_api_contract.md) |
| 2026-10-11 | `local_land_store` accepted. | [local_land_store.md](../specs/local_land_store.md) · [acceptance](../validations/local_land_store.md) |
| 2026-10-12 | `add_land` accepted. | [add_land.md](../specs/add_land.md) · [acceptance](../validations/add_land.md) |
| 2026-10-12 | `suggested_questions` accepted. | [suggested_questions.md](../specs/suggested_questions.md) · [acceptance](../validations/suggested_questions.md) |
| 2026-10-12 | `source_catalog_validation` accepted. | [source_catalog_validation.md](../specs/source_catalog_validation.md) · [acceptance](../validations/source_catalog_validation.md) |
| 2026-10-12 | `chat_question_submission` accepted. | [chat_question_submission.md](../specs/chat_question_submission.md) · [acceptance](../validations/chat_question_submission.md) |
| 2026-10-13 | `visual_foundation` added as a feature definition and wired as a dependency of the themed features. | `feature_list.json` |
| 2026-10-13 | Reconciled existing acceptance records. | `docs/validations/` |
| 2026-10-13 | `visual_foundation` accepted. | [visual_foundation.md](../specs/visual_foundation.md) · [acceptance](../validations/visual_foundation.md) |
| 2026-10-13 | `source_retrieval` accepted. | [source_retrieval.md](../specs/source_retrieval.md) · [acceptance](../validations/source_retrieval.md) |
| 2026-10-13 | `grounded_answer_generation` accepted. | [grounded_answer_generation.md](../specs/grounded_answer_generation.md) · [acceptance](../validations/grounded_answer_generation.md) |
| 2026-10-13 | `land_list` accepted. | [land_list.md](../specs/land_list.md) · [acceptance](../validations/land_list.md) |
| 2026-10-13 | `safe_abstention` accepted. | [safe_abstention.md](../specs/safe_abstention.md) · [acceptance](../validations/safe_abstention.md) |
| 2026-10-13 | `network_error_recovery` accepted. | [network_error_recovery.md](../specs/network_error_recovery.md) · [acceptance](../validations/network_error_recovery.md) |
| 2026-10-13 | `edit_land` accepted. | [edit_land.md](../specs/edit_land.md) · [acceptance](../validations/edit_land.md) |
| 2026-10-13 | `response_states` accepted. | [response_states.md](../specs/response_states.md) · [acceptance](../validations/response_states.md) |
| 2026-10-13 | `remove_land` accepted. | [remove_land.md](../specs/remove_land.md) · [acceptance](../validations/remove_land.md) |
| 2026-10-13 | `answer_source_cards` accepted. | [answer_source_cards.md](../specs/answer_source_cards.md) · [acceptance](../validations/answer_source_cards.md) |
| 2026-10-13 | `minimal_land_context` accepted. | [minimal_land_context.md](../specs/minimal_land_context.md) · [acceptance](../validations/minimal_land_context.md) |
| 2026-10-13 | `land_clarification` accepted. | [land_clarification.md](../specs/land_clarification.md) · [acceptance](../validations/land_clarification.md) |
| 2026-10-13 | `answer_land_scope` accepted. | [answer_land_scope.md](../specs/answer_land_scope.md) · [acceptance](../validations/answer_land_scope.md) |
| 2026-10-13 | `land_data_disclosure` accepted. | [land_data_disclosure.md](../specs/land_data_disclosure.md) · [acceptance](../validations/land_data_disclosure.md) |
| 2026-10-13 | `chat_accessibility` accepted. | [chat_accessibility.md](../specs/chat_accessibility.md) · [acceptance](../validations/chat_accessibility.md) |
| 2026-10-13 | `land_form_accessibility` accepted. | [land_form_accessibility.md](../specs/land_form_accessibility.md) · [acceptance](../validations/land_form_accessibility.md) |
| 2026-10-13 | `land_safety_evaluation` accepted. | [land_safety_evaluation.md](../specs/land_safety_evaluation.md) · [acceptance](../validations/land_safety_evaluation.md) |
| 2026-10-16 | `android_mvp_build` accepted. | [android_mvp_build.md](../specs/android_mvp_build.md) · [acceptance](../validations/android_mvp_build.md) |
| 2026-10-16 | `desktop_mvp_build` accepted. | [desktop_mvp_build.md](../specs/desktop_mvp_build.md) · [acceptance](../validations/desktop_mvp_build.md) |
| 2026-10-17 | Harness: separated the status board from on-demand detail. | `PROGRESS.md`, `docs/progress/current-state.md` |
| 2026-10-17 | Harness: made the feature index lean and moved behavior into specs. | `feature_list.json`, `docs/specs/<feature-id>.md` |
| 2026-10-17 | Harness: added focused, fast, and backend verification tiers. | `scripts/init.sh` |
| 2026-10-17 | Harness: split CI gates by change type. | `.github/workflows/gate.yml` |
| 2026-10-17 | Harness: moved the session log out of `PROGRESS.md`. | `docs/progress/session-log.md` |
| 2026-10-17 | Harness: consolidated feature-evidence records. | deleted `docs/progress/feature-evidence.md`; this log is now a one-line pointer index; canonical stores are `docs/validations/<feature-id>.md` (acceptance) and the spec's "Feature evidence" (raw verification) |
| 2026-10-17 | Harness: moved feature behavior and verification into spec metadata. | `feature_list.json`, `docs/specs/<feature-id>.md` |
| 2026-10-17 | Harness: separated spec contracts from research and evidence appendices. | `docs/specs/`, `feature_list.json`, `AGENTS.md`, `PROGRESS.md`, `.agents/skills/feature-{spec,implementer,flow,validator}/` |
| 2026-10-17 | Harness: shortened the on-demand product snapshot. | `docs/progress/current-state.md`, `PROGRESS.md`, `AGENTS.md` |
| 2026-10-17 | `backend_ask_endpoint` accepted. | [backend_ask_endpoint.md](../specs/backend_ask_endpoint.md) · [acceptance](../validations/backend_ask_endpoint.md) |
| 2026-10-17 | `backend_pac_corpus` accepted. | [backend_pac_corpus.md](../specs/backend_pac_corpus.md) · [acceptance](../validations/backend_pac_corpus.md) · [PAC coverage](../../knowledge/pac_coverage.md) |
| 2026-10-18 | `backend_campaign_validity` accepted. | [backend_campaign_validity.md](../specs/backend_campaign_validity.md) · [acceptance](../validations/backend_campaign_validity.md) |
| 2026-10-18 | `backend_answer_evaluation` accepted. | [backend_answer_evaluation.md](../specs/backend_answer_evaluation.md) · [acceptance](../validations/backend_answer_evaluation.md) |
| 2026-10-19 | `coverage_and_help` accepted. | [coverage_and_help.md](../specs/coverage_and_help.md) · [acceptance](../validations/coverage_and_help.md) |
| 2026-10-20 | `platform_ask_wiring` accepted. | [platform_ask_wiring.md](../specs/platform_ask_wiring.md) · [acceptance](../validations/platform_ask_wiring.md) |
| 2026-10-20 | `backend_citation_hardening` accepted. | [backend_citation_hardening.md](../specs/backend_citation_hardening.md) · [acceptance](../validations/backend_citation_hardening.md) |
| 2026-10-20 | `land_setup_fields_decision` accepted. | [land_setup_fields_decision.md](../specs/land_setup_fields_decision.md) · [acceptance](../validations/land_setup_fields_decision.md) |
| 2026-10-20 | `land_backup_decision` accepted. | [land_backup_decision.md](../specs/land_backup_decision.md) · [acceptance](../validations/land_backup_decision.md) |
| 2026-10-21 | `desktop_land_layout_decision` accepted. | [desktop_land_layout_decision.md](../specs/desktop_land_layout_decision.md) · [acceptance](../validations/desktop_land_layout_decision.md) |
| 2026-10-21 | `desktop_wide_land_layout` accepted. | [desktop_wide_land_layout.md](../specs/desktop_wide_land_layout.md) · [acceptance](../validations/desktop_wide_land_layout.md) |
| 2026-10-22 | Imported and indexed the Stitch design references. | [design-references/README.md](../../design-references/README.md), `DESIGN.md`, `ARCHITECTURE.md` |
| 2026-10-24 | Planned `shared_design_system` from the selected Stitch tokens. | `docs/specs/shared_design_system.md`, `docs/archive/specs/shared_design_system.appendix.md`, `DESIGN.md` |
| 2026-10-24 | `shared_design_system` accepted. | [shared_design_system.md](../specs/shared_design_system.md) · [acceptance](../validations/shared_design_system.md) |
| 2026-10-25 | `ui_refresh_accessibility_audit` accepted. | [ui_refresh_accessibility_audit.md](../specs/ui_refresh_accessibility_audit.md) · [acceptance](../validations/ui_refresh_accessibility_audit.md) |
| 2026-10-25 | `help_privacy_refresh` accepted. | [help_privacy_refresh.md](../specs/help_privacy_refresh.md) · [acceptance](../validations/help_privacy_refresh.md) |
| 2026-10-25 | Removed the custom typography override. | `docs/validations/shared_design_system.md` · `DESIGN.md` |
| 2026-10-25 | `design_token_refresh` accepted. | [design_token_refresh.md](../specs/design_token_refresh.md) · [acceptance](../validations/design_token_refresh.md) |
| 2026-10-25 | `screenshot_regression_tests` accepted. | [screenshot_regression_tests.md](../specs/screenshot_regression_tests.md) · [acceptance](../validations/screenshot_regression_tests.md) |
| 2026-10-25 | Split screenshot captures by screen and added phone-width scenes. | [shared/src/jvmTest/screenshots/README.md](../../shared/src/jvmTest/screenshots/README.md) · `docs/archive/specs/screenshot_regression_tests.appendix.md` |
| 2026-10-25 | Added Android host-rendered screenshot coverage. | `docs/screenshot-regression.md` · `docs/validations/screenshot_regression_tests.md` |
| 2026-10-25 | `brand_vectors` accepted. | [brand_vectors.md](../specs/brand_vectors.md) · [acceptance](../validations/brand_vectors.md) |
| 2026-10-25 | `ui_component_library` accepted. | [ui_component_library.md](../specs/ui_component_library.md) · [acceptance](../validations/ui_component_library.md) |
| 2026-10-25 | `app_chrome_navigation` accepted. | [app_chrome_navigation.md](../specs/app_chrome_navigation.md) · [acceptance](../validations/app_chrome_navigation.md) |
| 2026-10-25 | Post-acceptance update to `app_chrome_navigation`. | [app_chrome_navigation.md](../specs/app_chrome_navigation.md) · [acceptance](../validations/app_chrome_navigation.md) |
| 2026-10-25 | `land_measurement_fields` accepted. | [land_measurement_fields.md](../specs/land_measurement_fields.md) · [acceptance](../validations/land_measurement_fields.md) |
| 2026-10-25 | `land_search_and_summary` accepted. | [land_search_and_summary.md](../specs/land_search_and_summary.md) · [acceptance](../validations/land_search_and_summary.md) |
| 2026-10-25 | `chat_screen_refresh` accepted. | [chat_screen_refresh.md](../specs/chat_screen_refresh.md) · [acceptance](../validations/chat_screen_refresh.md) |
| 2026-10-25 | `lands_screens_refresh` accepted. | [lands_screens_refresh.md](../specs/lands_screens_refresh.md) · [acceptance](../validations/lands_screens_refresh.md) |
| 2026-10-27 | `official_source_monitoring` accepted. | [official_source_monitoring.md](../specs/official_source_monitoring.md) · [acceptance](../validations/official_source_monitoring.md) |
| 2026-10-27 | `official_source_discovery` accepted. | [official_source_discovery.md](../specs/official_source_discovery.md) · [acceptance](../validations/official_source_discovery.md) |
| 2026-10-27 | `recover_removed_lands` accepted. | [recover_removed_lands.md](../specs/recover_removed_lands.md) · [acceptance](../validations/recover_removed_lands.md) |
| 2026-10-27 | `local_land_auto_backup` accepted. | [local_land_auto_backup.md](../specs/local_land_auto_backup.md) · [acceptance](../validations/local_land_auto_backup.md) |
| 2026-10-27 | `official_document_candidate_ingestion` accepted. | [official_document_candidate_ingestion.md](../specs/official_document_candidate_ingestion.md) · [acceptance](../validations/official_document_candidate_ingestion.md) |
| 2026-10-27 | `legal_change_impact_analysis` accepted. | [legal_change_impact_analysis.md](../specs/legal_change_impact_analysis.md) · [acceptance](../validations/legal_change_impact_analysis.md) |
| 2026-10-27 | `knowledge_update_review_pr` accepted. | [knowledge_update_review_pr.md](../specs/knowledge_update_review_pr.md) · [acceptance](../validations/knowledge_update_review_pr.md) |
| 2026-10-27 | `pac_evidence_expansion` accepted. | [pac_evidence_expansion.md](../specs/pac_evidence_expansion.md) · [acceptance](../validations/pac_evidence_expansion.md) |
| 2026-10-27 | `hosting_provider_review` accepted. | [hosting_provider_review.md](../specs/hosting_provider_review.md) · [acceptance](../validations/hosting_provider_review.md) |
| 2026-10-27 | `hosted_pilot_operations` accepted (prepared, not deployed). | [hosted_pilot_operations.md](../specs/hosted_pilot_operations.md) · [acceptance](../validations/hosted_pilot_operations.md) |
| 2026-10-27 | `local_bge_m3_embeddings` accepted. | [local_bge_m3_embeddings.md](../specs/local_bge_m3_embeddings.md) · [acceptance](../validations/local_bge_m3_embeddings.md) |
| 2026-10-31 | `pilot_privacy_readiness` accepted (gates closed; qualified review pending). | [pilot_privacy_readiness.md](../specs/pilot_privacy_readiness.md) · [acceptance](../validations/pilot_privacy_readiness.md) |
| 2026-10-31 | `portable_land_backup` accepted. | [portable_land_backup.md](../specs/portable_land_backup.md) · [acceptance](../validations/portable_land_backup.md) |
| 2026-10-31 | `knowledge_update_scheduler` accepted (owned-host templates, not installed). | [knowledge_update_scheduler.md](../specs/knowledge_update_scheduler.md) · [acceptance](../validations/knowledge_update_scheduler.md) |
| 2026-10-31 | `chroma_hybrid_retrieval` accepted (opt-in; BM25 stays default, no answer-level gain measured). | [chroma_hybrid_retrieval.md](../specs/chroma_hybrid_retrieval.md) · [acceptance](../validations/chroma_hybrid_retrieval.md) |
| 2026-10-31 | `gemini_generation_provider` accepted (gate closed; no transport shipped). | [gemini_generation_provider.md](../specs/gemini_generation_provider.md) · [acceptance](../validations/gemini_generation_provider.md) |
| 2026-10-31 | `local_generation_provider` accepted (off by default; measured on owner Mac, host decision pending). | [local_generation_provider.md](../specs/local_generation_provider.md) · [acceptance](../validations/local_generation_provider.md) |
| 2026-10-31 | `knowledge_reindex_release` accepted (local rehearsal only; no host step executed, Chroma packaging untested). | [knowledge_reindex_release.md](../specs/knowledge_reindex_release.md) · [acceptance](../validations/knowledge_reindex_release.md) |
| 2026-11-01 | `mock_answer_server` accepted (Kotlin/Ktor mock on loopback; Desktop/emulator walkthroughs not yet run). | [mock_answer_server.md](../specs/mock_answer_server.md) · [acceptance](../validations/mock_answer_server.md) |
| 2026-11-01 | `local_service_connection` accepted (test builds only; manual GUI checks not run). | [local_service_connection.md](../specs/local_service_connection.md) · [acceptance](../validations/local_service_connection.md) |
| 2026-11-01 | `local_rag_bootstrap` accepted (owner walkthrough passed on the owner's Mac; Ollama-closed case not run live). | [local_rag_bootstrap.md](../specs/local_rag_bootstrap.md) · [acceptance](../validations/local_rag_bootstrap.md) |
| 2026-11-01 | `numeric_grounding_check` accepted (lexical Spanish numeric/date/deadline check in `verify_draft`; fixtures only, live local-model effect not measured). | [numeric_grounding_check.md](../specs/numeric_grounding_check.md) · [acceptance](../validations/numeric_grounding_check.md) |
| 2026-11-01 | `local_full_rag_stack` accepted (start/stop/status commands; owner walkthrough passed on the owner's Mac; no app question sent). | [local_full_rag_stack.md](../specs/local_full_rag_stack.md) · [acceptance](../validations/local_full_rag_stack.md) |
| 2026-11-01 | `backend_container_image` accepted (container build/start/status/stop commands; owner walkthrough passed on the owner's Mac with Docker Desktop; no app question sent). | [backend_container_image.md](../specs/backend_container_image.md) · [acceptance](../validations/backend_container_image.md) |
