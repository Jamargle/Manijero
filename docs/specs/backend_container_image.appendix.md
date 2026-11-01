# backend_container_image — appendix

## Repository research

### Files inspected

- `docs/constraints/operations.md` — owner-operability MUSTs (one named command, prerequisites first, `Result:` line, idempotent re-runs, owner guide, walkthrough with a missing-prerequisite case and a recovery) and the `local_full_rag_stack` loopback-start MUST this feature mirrors.
- `docs/constraints/lands.md` — local generation transport rule: only the `OLLAMA_BASE_URL` constant `http://127.0.0.1:11434`, pinned digest, tests never need Ollama; the relay note attaches here.
- `docs/constraints/hosting-and-pilot.md` — pilot must start only through `serve_pilot.py`; this container is a default-profile local runtime, not a pilot launcher (reconciling is `qa_server_deployment`).
- `docs/specs/local_full_rag_stack.md` + appendix — accepted contract shape, seven-key launch environment, port-owner rules, run record, walkthrough format; lists this feature as a dependent and a non-goal there.
- `scripts/init.sh` — early `--local-rag-*` dispatch blocks (misuse exit 2, port validation, dev-env link via `python-env.sh dev --if-present`), `usage`, `--check` listing, mock port-in-use message (line ~574).
- `backend/app/local_rag_service.py` — `launch_environment`, `address_lines`, `answers_check`, `drafting_check`, `_check_port`, `LoopbackProbe`, `port_from_environment`, `PORT_ENV`, `INHERITED_KEYS`, lock and record helpers.
- `backend/app/local_rag_bootstrap.py` — `LocalPaths` layout (`models/bge-m3`, `knowledge-releases`, `logs`, `settings.env`), `PARTS`/`REASONS`, `inspect`, `status_lines`, `RunLog`, `OllamaClient`, `GitCheckout`, `REPOSITORY_ROOT`, test-only env pattern (`MANIJERO_LOCAL_HOME`, `MANIJERO_OLLAMA_CLI`).
- `backend/app/vector_store.py` — `chromadb.PersistentClient(path=…)` opens the store in place, so the store must be writable by the service user.
- `backend/app/ask_api.py`, `knowledge_release.py`, `embedding_index.py`, `vector_store.py` — paths derived from `parents[2]`; with the release root set the service reads the release, not `knowledge/` (to be confirmed by the staged-layout smoke).
- `backend/requirements.txt` (ranges), `requirements-embeddings.txt` (exact torch/transformers pins), `requirements-hybrid.txt` (`-r` both plus `chromadb==1.5.9`), `backend/deploy/requirements-production.txt` (exact fastapi/uvicorn/httpx; transitive not hash-pinned), `.python-version` (`3.12`).
- `backend/tests/test_local_rag_commands.py` — subprocess pattern (temporary home, empty venv root, fake CLI, skip without `backend/.venv`).
- `docs/owner-guide.md` headings — section and walkthrough style to extend.
- `ARCHITECTURE.md`, `PROGRESS.md` "Current state", `feature_list.json` (dependent `qa_server_deployment`).
- No `Dockerfile`, `.dockerignore`, or compose file exists in the repository. Not inspected: `serve_pilot.py`, `pilot_config.py` internals, `scripts/python-env.sh` internals.

### Planner decisions (not owner decisions; the owner may change them before implementation)

- Self-contained image: code, pinned runtime, the published release (with its Chroma store), and the pin-verified `bge-m3` model, so `qa_server_deployment` ships one artifact; drafting stays on host Ollama (owner decision 2).
- Native platform only (linux/arm64 on the owner's Apple-silicon Mac); torch from `https://download.pytorch.org/whl/cpu` so no GPU libraries enter the image. Other platforms are `qa_server_deployment`.
- Same port 8000 and app addresses as `--local-rag-start`; only one of the two runs at a time (port-owner check).
- Tag `manijero-backend:<release-id>-<commit12>` plus moving tag `manijero-backend:local`; start runs `local`.
- Start requires image release = published release and image campaign = settings campaign, mirroring "start only when its status is all OK".
- Build refuses uncommitted changes in copied tracked paths, so the revision label is true.
- No `--read-only` root filesystem: Chroma may write lock/journal files when it opens.

### Fixed build and run arguments

- Build: `docker build --file backend/container/Dockerfile --build-context knowledge-release=<home>/knowledge-releases/releases/<id> --build-context embedding-model=<home>/models/bge-m3 --build-arg BASE_IMAGE=<tag>@<digest> --build-arg RELEASE_ID=<id> --build-arg LOCAL_MODEL=<record tag> --label <each label> --tag manijero-backend:<id>-<commit12> --tag manijero-backend:local --progress plain <repo root>`; BuildKit is Docker Desktop's default.
- Allowlist (`Dockerfile.dockerignore`, `*` then `!` entries): `backend/app/`, `backend/config/`, `backend/requirements*.txt`, `backend/deploy/requirements-production.txt`, `backend/container/`, plus any `knowledge/` schema the staged smoke proves the service reads at runtime; never `tests/`, `.venv*`, `*.env`, `deploy/*.example`, caches.
- Image layout: `/opt/manijero/backend/{app,config,container}`, `/opt/manijero/knowledge-releases/{releases/<id>,current -> releases/<id>}`, `/opt/manijero/models/bge-m3`, `/opt/manijero/pip-freeze.txt`; user `manijero` (uid 10001); `WORKDIR /opt/manijero/backend`; `EXPOSE 8000`; `ENTRYPOINT ["python", "/opt/manijero/backend/container/entrypoint.py"]`.
- Run: `docker run --detach --init --name manijero-backend --label org.manijero.managed=1 --publish 127.0.0.1:<port>:8000 --env MANIJERO_ACTIVE_CAMPAIGN=<settings> --cap-drop ALL --security-opt no-new-privileges --restart no manijero-backend:local`.
- Stop: `docker stop --time 10 manijero-backend`, `docker logs` into the log, `docker rm manijero-backend` — each only after `docker inspect` shows the label.
- Relay check (status): `docker exec manijero-backend python /opt/manijero/backend/container/ollama_relay.py --check` (exit 0 when `/api/tags` answers through the relay).
- `base-image.json`: `{"image": "python:3.12-slim-bookworm", "digest": "sha256:<64 hex index digest>", "reviewed_on": "YYYY-MM-DD", "reason": "..."}`. The implementer reads the index digest from the registry's anonymous manifest API (free) and records the method in evidence; the owner's first build proves it resolves.

### Current gaps

- Docker is not installed on this Mac: the Dockerfile, BuildKit named contexts, `host.docker.internal` reachability of a loopback-only Ollama, and the image size are proven only by the owner walkthrough.
- `test_local_container_commands.py` cannot run the no-dev-environment branch (module skips without `backend/.venv`); checked by reading `init.sh`.

## Implementation plan

1. Write `backend/container/ollama_relay.py`: constants `LISTEN = ("127.0.0.1", 11434)`, `TARGET = ("host.docker.internal", 11434)`; `serve(listen, target)` (test-only parameters) with bounded threads; `--check`.
2. Write `backend/container/entrypoint.py`: `uvicorn_config()` (app `app.main:app`, host `0.0.0.0`, port 8000, no reload, no access log); `main()` starts the relay daemon thread, then runs uvicorn; exits non-zero if the relay cannot bind.
3. Write `base-image.json`, `Dockerfile`, `Dockerfile.dockerignore` per the fixed arguments above.
4. Write `backend/app/local_container.py`: constants and sentences, `DockerCli` port plus `SystemDockerCli`, label helpers, `image_inputs` (commit, release, campaign, pins), `build_argv`, `run_argv`.
5. Add `run_build` (prerequisites → up-to-date check → build with minute ticker → verify labels → result), `run_start`, `run_status`, `run_stop`, the `.container.lock`, and leftover-container handling.
6. Extend `backend/scripts/local_rag.py` with the four choices and Ctrl+C sentences (build: nothing tagged; start: container removed).
7. Change the port-in-use sentence in `local_rag_service.py` and the mock block in `init.sh`; add the `--container-*` dispatch, `usage`, `--check` listing.
8. Write the three test files; update `test_local_rag_service.py` for the sentence.
9. Update `docs/owner-guide.md`, `backend/README.md`, `ARCHITECTURE.md`, `operations.md`, `lands.md`, `risks-and-open-questions.md`.
10. Run the focused block and `./scripts/init.sh --fast`; record one-line results.
11. Hand the walkthrough to the orchestrator for the owner; record results.

## Verification plan

- Focused block (contract): offline, all pass; `./scripts/init.sh --fast`: no regression.
- `test_local_container.py` (in-memory fake Docker, fake probe, fake Ollama, temporary home and copied knowledge as in the bootstrap tests):
  - build ready: exact `build_argv` (contexts, args, every label, both tags); ticker lines with a fake clock; result line; exit 0;
  - build up to date: zero `build` calls, `local` retagged, exit 0;
  - build prerequisites (Docker missing, daemon closed, never set up, each image part not OK, dirty copied path, bad base pin, lock held): fix named, zero `build` calls, home unchanged, exit 1;
  - build failure and Ctrl+C: no tag call, log path, exit 1, running container untouched;
  - start ready: exact `run_argv` (host publish `127.0.0.1`, only the campaign env, label, `--init`, `--cap-drop ALL`); waits for health and ready; addresses; exit 0;
  - start blocked (no image, older release, other campaign, Ollama closed, digest mismatch, port owners mock/local-rag/foreign backend/other, unlabeled `manijero-backend`): named step, zero `run` calls, exit 1;
  - already running (OK / problem) and leftover stopped container cleared; start failures (exit, health timeout, ready 503, Ctrl+C): logs saved, container removed, exit 1;
  - status: all OK; each PROBLEM (answers, search, host Ollama, relay check); not running and Docker closed make zero probes;
  - stop: stop, logs, remove; not running; Docker closed; unlabeled container never touched;
  - bad port values exit 2; no output, label, or log line contains a corpus sentinel string.
- `test_container_image_files.py` (static and in-process, no Docker):
  - `FROM` uses exactly `BASE_IMAGE` and `base-image.json` holds a tag plus a 64-hex digest;
  - Dockerfile sets a non-root `USER`, the seven-key environment equals `local_rag_service.launch_environment` keys with image paths, installs `requirements-hybrid.txt` with the production constraints and the CPU index, never mentions `ollama`, `--reload`, or a pilot key;
  - the image environment plus a campaign passes the real gates: `backend_from_environment(env)` is not `Bm25Backend`, `resolve_local_provider(…)` resolves `local` with a fake transport;
  - dockerignore is an allowlist that excludes `tests/`, `.venv*`, `*.env`, `deploy/*.example`;
  - `entrypoint.uvicorn_config()` fixed values; the relay forwards bytes both ways between two ephemeral loopback sockets, closes on either side, and its module constants are exactly the listen and target above; `--check` exit codes against a fake `/api/tags`;
  - staged-layout smoke: copy the allowlisted files into a temporary `/opt/manijero`-shaped tree with a fixture release under `knowledge-releases`, start `create_app` there in a subprocess (BM25, extractive) and `GET /health` and `/ready` through `TestClient` → ready; proves the allowlist holds everything the service imports and reads.
- `test_local_container_commands.py` (subprocess through `init.sh`, fake Docker executable recording argv, never a real container):
  - each command with Docker missing (`MANIJERO_DOCKER_CLI` pointing nowhere): exits 1/1/1/0 with the install sentence or nothing-to-stop;
  - fake daemon closed: build and start exit 1 naming Docker Desktop; status exit 1;
  - empty home with fake daemon open: build and start name `--local-rag-setup`, home not created;
  - extra argument for each command and a bad port: exit 2.
- E2E: not applicable; app-to-service checks are `local_end_to_end_smoke`.
- Owner walkthrough (operations.md MUST; the owner runs it exactly as `docs/owner-guide.md` writes it, from a fresh checkout; agents do not run it). For each step the owner reports the `Result:` line and anything different:
  1. Install Docker Desktop per the guide's one-time section; open it once. Report the version shown in **About**.
  2. `./scripts/init.sh --local-rag-status` → `Result: all 6 parts are ready.`; `./scripts/init.sh --local-rag-service-status` → not running (otherwise `--local-rag-stop`).
  3. Missing prerequisite: quit Docker Desktop; `./scripts/init.sh --container-build` → the open-Docker line and `Result: the image was not built. …`.
  4. Open Docker Desktop, wait for running; `--container-build` → built result; report the tag, size, and minutes taken.
  5. `--container-build` again → `Result: nothing new was built; …`.
  6. `--container-start` → started result and the two addresses.
  7. Close Terminal, open a new one; `--container-start` → already running.
  8. `--container-status` → four `OK` lines and the running result.
  9. Recovery: quit Ollama; `--container-status` → `PROBLEM  Drafting …` and attention result; open Ollama, wait 10 seconds, run again → all `OK`.
  10. `--container-stop` → stopped; again → nothing to stop; `--container-status` → not running.

## Evidence to capture

- Focused block and `--fast`: one-line results; the base-image digest source and date.
- Test names covering scenarios 1–12.
- Walkthrough steps 1–10: `Result:` line and exit code each, image tag, size, build minutes, release id, and whether the build log mentions any `nvidia` package. No question or corpus text.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-01, implementer session 1 (status left `in_progress`):

- `./scripts/init.sh --feature backend_container_image`: 169 passed, 2 skipped, 1 failed. The only failure is `test_container_image_files.py::test_the_base_image_is_pinned_by_tag_and_index_digest`: `base-image.json` has an empty `digest`/`reviewed_on`.
- `CI=true ./scripts/init.sh --fast`: backend 1611 passed, 4 skipped, 1 failed (the same digest test); contract examples and the five evaluators `[ok]`; `gradle-jvm-test` could not run because this sandbox has no Java runtime ("Unable to locate a Java Runtime"). No Kotlin file changed.
- `CI=true ./scripts/init.sh --verify`: not run, because `--fast` did not pass (and Gradle needs Java).
- **Blocker: base-image digest.** Reading the index digest of `python:3.12-slim-bookworm` from the anonymous registry API (`auth.docker.io` token, then a `HEAD` on `registry-1.docker.io/v2/library/python/manifests/3.12-slim-bookworm` with the OCI index `Accept` header, read `Docker-Content-Digest`) needs network access, which this session was not allowed. No digest was guessed. To fix: record `digest` (`sha256:<64 hex>`) and `reviewed_on` in `backend/container/base-image.json`. Until then `--container-build` refuses with the developer-fix line (scenario 3, tested).
- Test coverage by scenario: 1 `test_build_when_ready_runs_the_fixed_build_and_reports_the_tag`, `test_build_output_goes_only_to_the_log_file`; 2 `test_build_again_builds_nothing_and_points_local_at_the_image`; 3 `test_a_missing_build_prerequisite_*` (10 cases), `test_every_failed_build_prerequisite_is_listed_*`, commands-file Docker missing/closed/empty-home tests; 4 `test_a_failed_build_moves_no_tag_and_names_the_log`, `test_ctrl_c_during_the_build_*`; 5 `test_start_when_ready_*`, `test_start_on_a_custom_port_*`; 6 `test_a_blocked_start_*` (12 cases); 7 `test_start_while_running_*`, `test_a_stopped_leftover_container_*`; 8 `test_a_failed_start_*` (5 cases); 9 `test_status_*`; 10 `test_stop_*`, `test_a_container_without_the_manijero_label_*`; 11 `test_a_bad_port_is_misuse_*`, `test_an_extra_argument_or_a_bad_port_is_misuse`; 12 `test_no_output_label_or_log_line_contains_corpus_text`, the Dockerfile/allowlist/relay tests, and the staged-layout smoke `test_the_allowlisted_files_start_the_service_in_the_image_layout` (health and ready `200` from only the allowlisted files; no `knowledge/` schema is needed at runtime).
- Deviations, all within the contract: `test_local_rag_service.py` also adds `local_container` to the "service never imports operator modules" list (that test otherwise fails on the new operator module); the production pins are installed as `--requirement`, not `--constraint`, because pip rejects the `uvicorn[standard]` extra in a constraints file; the allowlist names the three runtime requirements files rather than `backend/requirements*.txt`, so `requirements-dev.txt` stays out.
- Owner walkthrough: not run (agents do not run it; Docker Desktop is not installed).

2026-11-01, implementer session 2 (status set to `passing`):

- Base-image digest recorded in `backend/container/base-image.json`: `sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337` (OCI multi-platform index of `python:3.12-slim-bookworm`). The owner supplied it through the coordinator, read on 2026-11-01 from the anonymous registry manifest API; `reviewed_on` is `2026-11-01`. The stale "until a developer records it" clause was removed from `reason`.
- `./scripts/init.sh --feature backend_container_image`: 170 passed, 2 skipped.
- `CI=true ./scripts/init.sh --fast`: all 9 offline checks passed (backend 1612 passed, 4 skipped; gradle-jvm-test ok with the Gradle-provisioned Zulu JDK 21).
- `CI=true ./scripts/init.sh --verify`: Fast tier passed; Full tier passed (Android host tests, debug APK, Desktop build).
- The session 1 blockers (digest, Java) are resolved. The owner walkthrough (steps 1–10) is still outstanding and needs Docker Desktop.

## Validator checklist

- [ ] Scope matches the contract; non-goals respected (no Ollama in the image, no service, pin, requirements, contract, or settings-key change, no pilot path, no LAN publish, no registry).
- [ ] Every build and start prerequisite is checked before any build, container creation, or write; each line names its fix.
- [ ] `build_argv` and `run_argv` match the fixed arguments; the image environment passes the real hybrid and local-provider gates in tests.
- [ ] The relay listens only on container loopback and targets only the constant `host.docker.internal:11434`; `OLLAMA_BASE_URL` and `local_generation.py` are unchanged.
- [ ] Only containers with the Manijero label are ever stopped or removed; re-running each command reports the current state.
- [ ] Dockerfile pins the base by digest, runs non-root, uses the allowlist; the staged-layout smoke passes.
- [ ] Output is plain sentences with one `Result:` line; Docker output only in printed logs; no corpus or personal text.
- [ ] Focused block runs unchanged via `./scripts/init.sh --feature backend_container_image` with no Docker, Ollama, or model.
- [ ] Owner walkthrough steps 1–10 recorded, including step 3 (missing prerequisite) and step 9 (recovery).
- [ ] Durable docs updated (owner guide, README, ARCHITECTURE, operations MUST, lands relay note, risks); nothing restated across files.
- [ ] `feature_list.json` and `PROGRESS.md` updated correctly at acceptance.
