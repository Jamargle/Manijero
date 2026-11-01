# Set up every local RAG artifact with one guided command and a plain-language status check

## Source metadata

- `id`: local_rag_bootstrap · `area`: operations · `depends_on`: local_bge_m3_embeddings, chroma_hybrid_retrieval, local_generation_provider, knowledge_reindex_release (all accepted) · `status` at planning: not_started
- User-visible behavior: the owner runs `./scripts/init.sh --local-rag-setup` once; it checks prerequisites, shows what it will download and how big it is, asks for confirmation, then downloads the pinned `bge-m3` model and the pinned Ollama model, builds the passage index, the Chroma store, and a published local knowledge release. `./scripts/init.sh --local-rag-status` reports each part in plain words. Re-running setup reports the current state and never re-downloads what is present and verified.
- Verification: offline tests with fake downloader, fake Ollama, and fake subprocess runner; no real download, no running Ollama, no `torch`/`chromadb` (commands in Focused verification).
- Notes: owner decisions 2026-11-01 — one guided setup command plus one status command following [`docs/constraints/operations.md`](../constraints/operations.md); sizes shown before anything starts (bge-m3 ~2.3 GB, pinned Mistral Small 24B ~15 GB) and confirmed; the command never installs Ollama (it stops and names the install step); re-runs report state without re-downloading; reuse the four dependencies' pieces with no new framework or dependency; focused verification uses fakes only.

## Goal

Give the owner one command that takes a machine with Ollama installed from nothing to every local RAG artifact present, verified against its reviewed pin, and current for the checked-out knowledge, plus one read-only command that says in plain words what is ready and what to do next. Later features (`local_full_rag_stack`) start the service on top of these artifacts.

## Non-goals

- Installing Ollama, uv, Python, or git; starting, stopping, or configuring the answer service; enabling `MANIJERO_RETRIEVAL_MODE=hybrid` or `MANIJERO_GENERATION_PROVIDER=local` (that is `local_full_rag_stack`).
- QA or prod environments and multi-profile settings (`environment_profiles`); monitoring or a dashboard.
- Changing any pin (`backend/config/bge_m3_embedding.json`, `local_generation_model.json`, `hybrid_retrieval.json`), the release gates, retrieval, generation, `contracts/`, or canonical `knowledge/` files.
- Uninstall, deleting downloaded models, garbage-collecting old releases, or reusing a model folder at another path.
- Knowledge review or merge; any legal-coverage or answer-quality claim. Windows (release roots are POSIX only).

## Job story

When I set up Manijero on my computer, I want one command that tells me what it will download, does it after I agree, and then tells me everything is ready, so I can run the full local answer service without knowing Python, models, or the terminal.

## Acceptance Scenarios

### 1. First run on a machine with Ollama running

Given Ollama is installed and running, no local home exists, and the checked-out knowledge files have no uncommitted changes · When the owner runs `./scripts/init.sh --local-rag-setup` and types `yes` · Then before anything is written it prints each pending download with its size computed from the pins (search model `bge-m3` 2.3 GB, drafting model Mistral Small 24B 15.2 GB, search software about 1.2 GB when the hybrid environment is not built yet) and the total; after `yes` it creates the commented settings file, builds the hybrid environment, downloads and verifies every pinned `bge-m3` file, builds the passage index, prepares a release with the index and Chroma store, publishes it, pulls the pinned Ollama model and confirms its digest, prints the six status lines all `OK`, ends with one result line, and exits `0`.

### 2. Ollama is missing

Given no `ollama` command is installed · When setup runs · Then it stops before creating, building, or downloading anything, says Ollama is not installed and the single step to fix it (install it from `https://ollama.com/download`, then run the same command again), and exits `1`.

### 3. Ollama is installed but not running

Given `ollama` exists but `http://127.0.0.1:11434` does not answer · When setup runs · Then it stops before changing anything, says to open the Ollama app and run the same command again, and exits `1`.

### 4. Other prerequisite missing

Given the knowledge files have uncommitted changes, or free disk space is below the pending downloads plus 1 GB, or another setup is already running · When setup runs · Then it stops before changing anything with one plain sentence naming what is wrong and the single step that fixes it, and exits `1`.

### 5. The owner declines

Given downloads are pending · When the owner answers anything other than `yes`/`y` (or input ends) · Then it prints that nothing was changed, writes no file, makes no download, and exits `1`.

### 6. Re-run when everything is current

Given a previous setup completed and nothing changed · When setup runs again · Then it asks nothing, downloads nothing, rebuilds nothing, prints the six `OK` lines, says everything is already set up, and exits `0`.

### 7. Re-run after an interruption or a damaged file

Given a previous run was interrupted, or one pinned `bge-m3` file is missing or differs from its pin · When setup runs · Then the confirmation lists only the bytes still missing, verified files are kept, only the missing or bad files are fetched, and the run continues from the first unfinished step.

### 8. Knowledge changed since the last release

Given models are present but the checked-out catalog, passages, cases, or the campaign setting differ from the published release · When setup runs · Then it downloads nothing and asks nothing, rebuilds the passage index and a new release, publishes it only if every release gate passes, and reports the result; a failed gate leaves the previous release in use, names the failure in plain words, prints the log path, and exits `1`.

### 9. A download or model does not match its pin

Given a downloaded `bge-m3` file fails its SHA-256 or size check, or the pulled Ollama model's digest differs from `local_generation_model.json` · When setup verifies it · Then the bad `bge-m3` file is discarded (the Ollama model is left as Ollama stores it), no pin is edited, the message says the download differs from the reviewed version and that a developer must review it, and the command exits `1`.

### 10. A step fails unexpectedly

Given a network error, a failed environment build, or any exception · When it happens · Then the terminal shows one plain sentence with the next step and the path of a log file under `<local home>/logs/`; the traceback and subprocess output are only in that log; finished parts are kept; exit is `1`. Ctrl+C prints that finished parts are kept and to run the same command again.

### 11. Status check

Given any state · When the owner runs `./scripts/init.sh --local-rag-status` · Then it prints six lines (search software, search model, passage index, vector store, knowledge release, drafting model), each `OK`, `MISSING`, or `PROBLEM` with what it means and the first thing to do, then one result line; it exits `0` only when all six are `OK`. It writes, downloads, and builds nothing, needs no `torch`/`chromadb`, and calls only loopback Ollama. Before the first setup it says setup has not run yet and names the setup command. Ollama not running is a `PROBLEM` line telling the owner to open Ollama.

## Technical approach

- **Commands.** `scripts/init.sh` dispatches `--local-rag-setup` and `--local-rag-status` at the top, next to `--backend`, before the Android, Java, and `local.properties` steps. Setup first checks the Ollama command (`${MANIJERO_OLLAMA_CLI:-ollama}`) in shell, then builds or links the dev environment with `scripts/python-env.sh dev`, then runs `backend/.venv/bin/python backend/scripts/local_rag.py setup`. Status links with `--if-present` (otherwise it prints "not set up yet") and runs `... local_rag.py status`. The owner types no variable. `MANIJERO_LOCAL_HOME` and `MANIJERO_OLLAMA_CLI` exist only for tests.
- **Local home.** Default is `$HOME/manijero/local`, holding `settings.env`, `models/bge-m3/`, `work/embedding-index.json`, `knowledge-releases/`, `logs/`, and `.setup.lock` (`fcntl.flock`). `settings.env` is commented and created on first confirmed setup with `MANIJERO_ACTIVE_CAMPAIGN=2026` (the existing `--backend` default). It is parsed as an allowlisted `KEY=VALUE` file, never sourced; an existing file is never overwritten, and an invalid value stops the command and names the line to fix. One `local_paths(home)` helper returns these paths for `local_full_rag_stack`.
- **Orchestration** (`backend/app/local_rag_bootstrap.py`, stdlib only, never imported by the service): `inspect(...)` returns one state per part (`ok|missing|problem` plus a fixed reason). `plan(...)` turns the states into ordered steps and the pending download bytes. `setup(...)` runs prerequisite checks, then the plan, then confirmation, then the steps. It uses injected ports for downloads, Ollama, subprocesses, prompt, disk usage, and clock, so tests use fakes. Sizes come from the pins (`files[].size` for missing or bad files, `size_bytes`) and are printed in GB with one decimal. The hybrid runtime shows as "about 1.2 GB" (measured in `backend/README.md`).
- **Prerequisites, all checked before any write:** the Ollama command exists; `GET /api/tags` answers through `local_generation.loopback_opener()`; `git status --porcelain` is empty for `knowledge/source_catalog.json`, `passages.json`, and `pac_answer_eval.json`; free space covers the pending bytes plus 1 GB on each target filesystem (local home, the venv root, and `$OLLAMA_MODELS` or `~/.ollama/models`); the lock is free.
- **Steps, in order, each skipped when its part is already `ok`:** (1) `scripts/python-env.sh hybrid`. (2) Download `bge-m3` with `backend/app/pinned_download.py`: HTTPS GET of `<source_url>/resolve/<model_revision>/<path>`, built only from the pin, HTTPS-only redirects, into `<file>.part`, then SHA-256 and size are checked and the file is renamed. Finish with `embeddings.verify_artifact`. (3) `.venv-hybrid` `manage_embeddings.py build --as-of <today UTC> --active-campaign <setting> --index work/embedding-index.json`. (4) `.venv-hybrid` `knowledge_release.py prepare --root knowledge-releases --embedding-index … --with-vector-store --code-revision <HEAD> --reviewed-baseline-revision <HEAD> --json` (the same approval form as the accepted focused verification). (5) `knowledge_release.py publish` when the gate passed and the release is not already current. (6) `ollama pull <pinned tag>` with progress shown, then confirm the `/api/tags` digest equals the record.
- **"Current" definitions** (shared by setup and status, manifest-level only):
  - Hybrid environment: `python-env.sh hybrid --if-present`.
  - Model: `verify_artifact` passes.
  - Release: `current` verifies, `gate.passed`, the input SHA-256s equal the checkout files, the campaign equals the setting, and the corpus is ready today.
  - Passage index and vector store: present in the current release with the configured model pin, using `embedding_index.index_status` at the release's `as_of` and `vector_store.manifest_status`.
  - Drafting model: the pinned tag is listed with the pinned digest.
  - A code-revision change alone does not trigger a rebuild.
- **Output.** Each step prints one progress line ("Step 3 of 6: …"). Messages are fixed English sentences (repository convention for operator output), and none contains corpus text, a question, or land data. Exit codes: `0` done or all OK; `1` stopped, cancelled, failed, or not all OK; `2` misuse.

## Expected file changes

- `backend/app/local_rag_bootstrap.py` — create; settings, `local_paths`, inspect/plan/setup/status, ports.
- `backend/app/pinned_download.py` — create; stdlib pinned-file downloader (per-file `.part`, hash and size check, HTTPS-only redirects).
- `backend/scripts/local_rag.py` — create; `setup` / `status` entry point.
- `scripts/init.sh` — modify; early dispatch of the two modes, `usage`, and the `--check` listing.
- `backend/tests/test_local_rag_bootstrap.py` — create; orchestration, plan, status, downloader with fakes.
- `backend/tests/test_local_rag_commands.py` — create; `init.sh` dispatch through subprocess with a temporary local home and a missing or fake Ollama command.
- `docs/owner-guide.md` — create; see below.
- `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`, `docs/risks-and-open-questions.md` — update; see below.
- Not changed: `backend/config/*`, `knowledge/*`, `contracts/*`, `embeddings.py`, `embedding_index.py`, `vector_store.py`, `knowledge_release.py`, `local_generation.py` (public functions reused as they are), requirements files.

## Visual design impact

UI involved: no. No app screen or Spanish app copy changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — add one bullet. `local_rag_bootstrap.py`/`pinned_download.py` are an operator-only setup layer that the service never imports. Their only network calls are the pinned upstream file URLs and loopback Ollama, and they compose the existing CLIs.
- `docs/constraints/operations.md`: update — add one MUST. A setup command may download only artifacts named by a reviewed pin, from the pin's own upstream location, and must verify each one against the pin before use. It never edits a pin to make a mismatch pass, and the answer service itself never downloads. Reason: `local_rag_bootstrap`.
- `AGENTS.md`: not needed — no workflow or repo-wide rule change.
- `docs/owner-guide.md`: create (operations.md requires it) — numbered copy-paste steps for "Set up the local answer tools" and "Check the local answer tools". Each step has the expected result and what to do when it differs (Ollama missing or not running, declined, interrupted, not enough space).
- `backend/README.md`: update — a short "One-command local setup" section (local home layout, steps, exit codes, logs, test-only variables) that links the owner guide. Name the command as the supported path in the bge-m3 "Download and verify" and the Ollama pull text.
- `docs/risks-and-open-questions.md`: update. The Ollama tag can move upstream, so a pull can fail closed on digest. The reviewed-baseline approval for the local release is an operator assertion. The real Chroma packaging path is exercised only by the owner walkthrough.
- `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed.

## Focused verification (required)

Offline, in the shared `backend/.venv`. No network, no Ollama, no model, no `torch`/`chromadb`. `test_local_rag_commands.py` calls `scripts/init.sh` with a temporary `MANIJERO_LOCAL_HOME` and a missing or fake `MANIJERO_OLLAMA_CLI`.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_local_rag_bootstrap.py tests/test_local_rag_commands.py tests/test_embeddings.py tests/test_knowledge_release.py tests/test_local_generation.py -q
```
<!-- verify:end -->

The operations.md owner walkthrough on the owner's Mac (real downloads, real Ollama) is a manual acceptance check listed in the appendix and is not part of this block.

## Appendix

See [`local_rag_bootstrap.appendix.md`](local_rag_bootstrap.appendix.md) for research, plan, evidence, and the validator checklist.
