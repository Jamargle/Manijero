# local_rag_bootstrap — appendix

## Repository research

### Files inspected

- `docs/constraints/operations.md`: the owner-operability MUSTs. It requires one named command, checking prerequisites before any change, a plain result line with a non-zero exit, idempotent re-runs, one commented settings file, the owner guide, and an acceptance walkthrough.
- `scripts/init.sh`: `--backend`/`--setup-python` are dispatched before the Android/Java/`local.properties` block. `--feature` runs the verify block with `bash -euo pipefail`. `--backend` defaults `MANIJERO_ACTIVE_CAMPAIGN=2026`.
- `scripts/python-env.sh`: builds or links the `dev`/`hybrid` shared envs. `--if-present` only links an env that already exists. It prints plain fixes when uv or Python is missing.
- `backend/config/bge_m3_embedding.json`: `source_url`, `model_revision`, and nine `files[]` entries with `sha256` and `size`, 2,293,315,747 bytes in total. The download URLs are derived from these fields.
- `backend/config/local_generation_model.json`: the pinned tag `mistral-small3.2:24b-instruct-2506-q4_K_M`, its `digest`, and `size_bytes` 15,177,384,862.
- `backend/app/embeddings.py`: `load_model_spec`, `verify_artifact` (stdlib-only; reports mismatched or missing files).
- `backend/app/embedding_index.py`: `index_status`, `read_index_document`. The `build` path runs through `backend/scripts/manage_embeddings.py build` (hybrid env).
- `backend/app/vector_store.py`: `read_manifest`, `manifest_status`. These do a manifest-only freshness check without `chromadb`.
- `backend/app/knowledge_release.py`: `prepare_release` (needs approval evidence), `publish`, `status`, `verify_release`, `current_release_id`. The CLI `backend/scripts/knowledge_release.py` supports `--json`.
- `backend/app/local_generation.py`: `loopback_opener()` (no proxy, no redirects), `load_local_model_record`, `evaluate_local_model_record`. `OllamaTransport._ensure_digest` shows how `/api/tags` is matched.
- `backend/README.md`: these sections describe the manual flow this feature automates. "Shared Python environments", "Local open-weight drafting", "Local multilingual embeddings", "Hybrid retrieval … Lifecycle", "Knowledge reindex and release". The hybrid env measures 1.2 GB.
- `docs/specs/knowledge_reindex_release.md`: its focused verification uses `--reviewed-baseline-revision "$(git rev-parse HEAD)"` for the current corpus, which is the precedent for the local release.
- `docs/constraints/answers-and-knowledge.md`: embedding models load only from verified local artifacts, the derived index lives outside `knowledge/`, and the reason given is "no download belongs on the answer-service host". Hence the new operations rule keeps downloading in the operator command.
- `docs/constraints/lands.md`: local generation talks only to loopback Ollama, uses only the pinned digest, and automated tests must not need Ollama.
- `feature_list.json`: `local_full_rag_stack` (start/stop/check service) and `environment_profiles` (multi-profile settings) depend on this feature and own the adjacent scope.
- `scripts/select-feature.sh`: the role comes from whether a spec exists, so planning leaves `status` unchanged.

### Existing patterns to follow

- Operator CLIs print fixed `key: value` output (or `--json`) and use exit codes `0`/`1`/`2`. Errors are fixed codes and never echo corpus text.
- Atomic writes (staging, then rename) and `O_CREAT|O_EXCL` or flock locks, as in `knowledge_release.py`.
- Heavy runtimes (`torch`, `chromadb`) run only in `.venv-hybrid` as subprocesses. Status-style checks stay in the dev env and are manifest-only.
- Tests inject clocks and openers (`OllamaTransport(opener=…, clock=…)`) instead of patching globals.

### Current gaps

- No owner guide exists. This feature creates `docs/owner-guide.md`.
- No pinned-file downloader exists. The README documents a manual `curl` loop.
- `manage_embeddings.py build` takes a fixed `--as-of`. The local release uses today in UTC, so the index is rebuilt together with every new release.
- The Chroma packaging path (`prepare --with-vector-store`) has only `importorskip` tests. Its first real run happens in the owner walkthrough.

## Implementation plan

1. Add `pinned_download.py`. `fetch_pinned_files(spec, target_dir, opener, progress)` skips files that already match the pin, downloads into `.part`, hashes while streaming, checks size and SHA-256, renames the file, and raises fixed codes (`download_failed`, `checksum_mismatch`, `size_mismatch`, `redirect_refused`).
2. Add `local_rag_bootstrap.py` in this order:
   - settings parse and create, `local_paths`;
   - `PartState` and `inspect` with the "current" rules from the contract;
   - `plan` (steps plus pending bytes per filesystem);
   - prerequisite checks;
   - `setup` and `status` renderers with fixed messages.
3. Define the ports (`Downloader`, `OllamaClient` with `cli_present`/`reachable`/`tags`/`pull`, `CommandRunner`, `Prompter`, `DiskProbe`, `Clock`) with real default implementations. The real `CommandRunner` streams to the log file.
4. Add `backend/scripts/local_rag.py` (`setup`, `status`). It catches every exception, writes the traceback to `logs/<command>-<UTC timestamp>.log`, and prints one sentence plus the log path.
5. Wire `scripts/init.sh`: early dispatch, the shell-side Ollama command check for setup, dev env build or link, `usage`, and the `--check` text.
6. Write `test_local_rag_bootstrap.py` and `test_local_rag_commands.py` (list below).
7. Write `docs/owner-guide.md`, then update the `backend/README.md` section, `ARCHITECTURE.md`, `operations.md`, and `risks-and-open-questions.md`.
8. Run the focused block, then `./scripts/init.sh --fast`. Record the results below.
9. Owner walkthrough on the owner's Mac (manual list below). Record a one-line result for each step.

## Verification plan

- Focused block (contract): offline, expected all pass.
- `./scripts/init.sh --fast`: no regression elsewhere.
- Tests in `test_local_rag_bootstrap.py` (each one names the behavior it covers):
  - missing Ollama command or Ollama not reachable: nothing is written, the fakes record zero downloads, pulls, and runs, and the message names the install or open step;
  - dirty knowledge files, low disk space, or a held lock: the command stops with nothing changed;
  - the plan lists only missing parts, with sizes from the pins (2.3 GB, 15.2 GB, hybrid about 1.2 GB only when absent) and the total;
  - declined answer or EOF: "nothing was changed", no files, exit 1;
  - accepted first run: steps run in order, `settings.env` is commented, and `prepare` receives `--embedding-index`, `--with-vector-store`, and `--reviewed-baseline-revision`/`--code-revision` set to HEAD; `publish` follows; all six lines are OK; exit 0;
  - re-run when everything is current: no prompt and no port calls except inspection; exit 0;
  - one bad or missing model file: only those bytes are listed and fetched;
  - checksum mismatch: the `.part` file is removed, other files are untouched, exit 1;
  - network error: finished files are kept, and the rerun resumes;
  - Ollama digest mismatch: the command fails closed, and the pin file is byte-identical;
  - changed knowledge or campaign: rebuild with no prompt; a failed gate keeps the previous `current` and exits 1;
  - status in each `OK`/`MISSING`/`PROBLEM` state, before setup, and with Ollama down: the directory snapshot is unchanged, `torch`/`chromadb` are not imported, and the exit code is correct;
  - an existing settings file is preserved, and an invalid campaign value names the line to fix;
  - no message contains passage text.
- Downloader tests: a fake opener serves tiny files against a temporary pin; non-HTTPS redirects are refused; the URL is built only from `source_url`/`model_revision`/`path`.
- `test_local_rag_commands.py`:
  - `init.sh --local-rag-setup` with `MANIJERO_OLLAMA_CLI=<missing>` exits 1, mentions `ollama.com/download`, and leaves the temporary local home empty;
  - `init.sh --local-rag-status` with an empty local home exits 1 and names `--local-rag-setup`;
  - a fake Ollama script plus an unreachable port gives the "open Ollama" message.
- Manual owner walkthrough (operations.md MUST), run exactly as the owner guide writes it. On the owner's Mac the Mistral model is already pulled, so only bge-m3 (2.3 GB) and possibly the hybrid environment download.
  - (a) Quit Ollama, then run setup. It stops and says "open Ollama".
  - (b) Open Ollama and run setup. It shows the sizes. Answer yes, then press Ctrl+C partway through the bge-m3 download.
  - (c) Run setup again. It resumes and ends all OK.
  - (d) Run setup a third time. It reports "already set up" and downloads nothing.
  - (e) Run status. All six lines are OK, exit 0.
- E2E: not applicable. No app, route, or wire change. The unit and subprocess tests cover the command surface.

## Evidence to capture

- Focused block and `--fast`: one-line results.
- Test names covering scenarios 1–11.
- Walkthrough steps (a)–(e): the result line, exit code, and download bytes shown for each.
- The release id published by the walkthrough, and the six status lines from step (e). No corpus text.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-01, implementer (this Mac; Ollama running with the pinned tag and digest):

- `./scripts/init.sh --feature local_rag_bootstrap`: 334 passed, 2 skipped. The skips are the two subprocess "Ollama closed" tests in `test_local_rag_commands.py`, which skip while a real Ollama serves 127.0.0.1:11434; the same path runs in-process with fakes.
- `CI=true ./scripts/init.sh --fast`: all 9 checks passed; backend tests 1396 passed, 4 skipped. No system JDK here, so `JAVA_HOME` pointed at Gradle's provisioned Zulu 21 (`~/.gradle/jdks`) for `gradle-jvm-test`.
- `--verify` was not run. No Android, Desktop, shared Kotlin, or packaging change.
- Scenario coverage (`test_local_rag_bootstrap.py` unless noted):
  1. `test_first_run_shows_downloads_asks_then_builds_everything_in_order`, `test_confirmation_sizes_come_from_the_pins` (real pins: about 1.2 / 2.3 / 15.2 GB, total about 18.7 GB; an edited record changes the figure).
  2–4. `test_a_missing_prerequisite_stops_before_any_change[ollama-missing|ollama-closed|knowledge-dirty|low-disk|lock-held]`, `test_free_space_is_checked_per_filesystem`; commands: `test_setup_without_ollama_names_the_install_step_and_changes_nothing`.
  5. `test_declining_changes_nothing[no|empty|nope|EOF]`.
  6. `test_rerun_when_everything_is_current_asks_and_downloads_nothing`, `test_existing_settings_file_is_never_overwritten`.
  7. `test_only_missing_or_damaged_model_files_are_listed_and_fetched` (138 bytes from the pin), `test_a_network_drop_keeps_finished_files_and_the_rerun_resumes` (`Range: bytes=10-`).
  8. `test_changed_knowledge_rebuilds_without_asking_and_publishes`, `test_a_failed_release_gate_keeps_the_previous_release`, `test_a_campaign_change_in_the_settings_triggers_a_rebuild`.
  9. `test_a_downloaded_file_that_differs_from_the_pin_is_discarded`, `test_an_ollama_digest_mismatch_fails_closed_without_editing_the_record`.
  10. `test_a_failed_environment_build_names_the_step_and_the_log`, `test_an_unexpected_exception_prints_one_sentence_and_logs_the_traceback`, `test_ctrl_c_keeps_finished_parts_and_says_to_run_again`.
  11. `test_status_before_setup_names_the_setup_command_and_writes_nothing`, `test_status_after_setup_is_all_ok_and_read_only`, `test_status_reports_each_problem_in_plain_words[6 cases]`, `test_status_runs_without_torch_or_chromadb` (subprocess with `torch`/`chromadb`/`transformers` blocked); commands: `test_status_before_setup_names_the_setup_command_and_writes_nothing`.
  - Settings, privacy, and downloader: `test_an_invalid_settings_line_is_named[4]`, `test_no_message_contains_corpus_text`, and six downloader tests (pin-only URL, skip of verified files, range ignored, oversize discarded, HTTPS-only redirect, no plain-HTTP handler).
- How the fakes work: the fake runner writes a real `passage-embedding-index-v1` file with synthetic vectors. It runs the real `knowledge_release.py prepare`/`publish` in process, with only `release_gates.package_vectors` replaced by a manifest-only store, and serves the fixture model from pin-derived URLs.
- Manual, temporary home, real pins, nothing downloaded:
  - `--local-rag-setup` with a missing CLI exits 1 and prints the install step.
  - With the real Ollama, answering `no` listed the hybrid environment (about 1.2 GB) and bge-m3 (2.3 GB), total about 3.5 GB. Mistral is already pulled here, so it was not listed. Exit 1, and the home was not created.
  - `--local-rag-status` showed 5 MISSING and drafting OK, with exit 1.
- Interpretations:
  - Store freshness uses the documents admitted today, as the hybrid backend checks. The index uses the release's `as_of`.
  - An interrupted `.part` file resumes with HTTP `Range` (scenario 7, "only the bytes still missing").
  - The drafting download is labelled with the pinned tag, because the record holds no display name.
- Owner walkthrough (a)–(e): **not run** by the implementer; run by the orchestrator below.

2026-11-01, orchestrator, owner walkthrough (owner decision 2026-11-01). Run on this Mac exactly as `docs/owner-guide.md` writes it, from a temporary detached worktree holding the branch state (removed afterwards), with the real `~/manijero/local` (empty at start) and real Ollama (Mistral already pulled):

- (a) Missing prerequisite, simulated by running setup with `/usr/local/bin` left off `PATH` (Ollama not quit or uninstalled): `Ollama is not installed…`, `Result: setup stopped before changing anything.`, exit 1, local home still empty. Before setup, `--local-rag-status` showed 5 MISSING and drafting OK, `Result: setup has not run yet…`, exit 1, nothing written.
- (b) Setup listed the hybrid environment (about 1.2 GB) and bge-m3 (2.3 GB), total about 3.5 GB. Answered `yes`. It ran `Step 1 of 5`…`Step 5 of 5`, printed six OK lines and `Result: everything is set up…`, exit 0, and published release `3050d1b8b5e10f82`. The first Ctrl-C attempt did not interrupt: a non-interactive `&` job ignores SIGINT, so the harness, not the product, failed.
- Recovery: `pytorch_model.bin` was moved aside. A new run, with SIGINT reset to default, listed only bge-m3 (2.3 GB), and SIGINT came at 624,951,296 bytes. It printed `Setup was stopped. Finished parts are kept…`, `Result: setup stopped; finished parts are kept.`, exit 1, and the `.part` file was kept.
- (c) Re-run listed `Search model bge-m3: 1.6 GB` (only the remaining bytes), six OK lines, `Result: everything is set up…`, exit 0. The resumed file was byte-identical (`cmp`) to the first download. The held copy was then deleted.
- (d) Third run with no input: six OK lines, `Result: everything is already set up. Nothing was downloaded or changed.`, exit 0, no prompt.
- (e) `--local-rag-status`: OK for search software, search model (bge-m3), passage index, vector store, knowledge release, drafting model; `Result: all 6 parts are ready.`, exit 0. `current` → `releases/3050d1b8b5e10f82`, release log has one event. The real Chroma packaging path (`prepare --with-vector-store`) passed here for the first time.
- Not exercised live: `Ollama is installed but not running` (quitting the shared Ollama was avoided). The in-process tests and the subprocess tests cover it, but the subprocess tests skip while a real Ollama serves port 11434. The settings-file campaign change was not run; tests cover it. The guide's `Step 1 of 6` is an example; with Mistral already present the setup counts 5 steps.
- `./scripts/init.sh --feature local_rag_bootstrap` after the `--android` help alignment fix: 334 passed, 2 skipped.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no service start, no provider/mode enabling, no pin edit, no Ollama install, no new dependency).
- [ ] Every prerequisite is checked before any write, and `MANIJERO_LOCAL_HOME` stays empty on each early stop.
- [ ] Sizes come from the pin files, not hard-coded model sizes. The confirmation comes before any download.
- [ ] Re-run with everything current makes no download, pull, build, or prompt.
- [ ] Downloads come only from pin-derived URLs and are verified before use. Ollama is reached only through loopback (plus its own CLI).
- [ ] Status is read-only, works without `torch`/`chromadb`, and exits 0 only when all six parts are OK.
- [ ] Output is plain sentences with one result line. Tracebacks go only to the printed log path. No corpus or personal text appears.
- [ ] Acceptance scenarios pass, with evidence. The owner walkthrough is recorded (a)–(e).
- [ ] Focused verification block runs unchanged through `./scripts/init.sh --feature local_rag_bootstrap`.
- [ ] Durable documentation impact followed (owner guide, README section, ARCHITECTURE bullet, operations MUST, risks); nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly.
