# Build and run the backend container image with one command each

## Source metadata

- `id`: backend_container_image · `area`: operations · `depends_on`: local_full_rag_stack (accepted) · `status` at planning: not_started
- User-visible behavior: the owner runs `./scripts/init.sh --container-build` to build a reproducible backend image that packages the published knowledge release and the pinned search model from `~/manijero/local`, `--container-start` to run it in Docker Desktop on this Mac with the same hybrid search and local drafting as `--local-rag-start`, `--container-status` to see in plain words whether it runs, can answer, and where the apps connect, and `--container-stop` to stop it. Re-running any command reports the current state.
- Verification: offline unit and subprocess tests with a fake Docker CLI, fake probes, and fake Ollama, plus static checks of the image files and a staged-layout smoke of the service (commands in Focused verification); the owner walkthrough in `docs/owner-guide.md` is the manual acceptance check.
- Notes: owner decisions recorded 2026-11-01:
  1. The container runtime is Docker Desktop (free for personal and small-business use). It is not installed on this Mac, so automated verification fakes Docker (test-only `MANIJERO_DOCKER_CLI`) and never needs Docker, Ollama, or a model. The owner installs Docker Desktop for the manual walkthrough in `docs/owner-guide.md`.
  2. Ollama stays outside the image, on the host Mac.
  3. Relay approach accepted: the backend's fixed loopback Ollama address and code stay unchanged; a small fixed relay inside the container forwards to `host.docker.internal:11434`; the Ollama-address rule in `docs/constraints/lands.md` gets a note citing this decision.
  4. Build, start, status, and stop are each one named `init.sh` command (`--container-build`, `--container-start`, `--container-status`, `--container-stop`) with plain-language `Result:` lines, mirroring the `--local-rag-*` commands (`docs/constraints/operations.md`).
  Zero budget: no paid service. Image contents, tag scheme, port, and native-platform build are planner choices (appendix, "Planner decisions").

## Goal

Turn the working local answer service into one self-contained, reproducible image (code, pinned runtime, knowledge release, search model) that the owner builds and runs with copy-paste commands, as the base that `qa_server_deployment` will ship, without learning Docker.

## Non-goals

- Ollama or any model weights for drafting inside the image; GPU support; publishing to a registry; pushing, saving, or copying the image to another machine; multi-platform builds (all `qa_server_deployment`).
- The pilot profile, authentication, retention, Gemini, QA/prod profiles (`environment_profiles`), TLS or tunnels, LAN or physical-device access (host publish is `127.0.0.1` only).
- Changing the answer service (`backend/app/main.py`, `ask_api.py`, retrieval, generation, `local_generation.py` and its `OLLAMA_BASE_URL`), `contracts/`, any pin in `backend/config/`, `knowledge/`, requirements files, or the settings-file keys; changing `--local-rag-setup`/`--local-rag-status` behavior.
- Building or repairing local artifacts (that is `--local-rag-setup`); installing or opening Docker Desktop or Ollama; deleting old images; start at login; monitoring (`monitoring_dashboard`); app end-to-end checks (`local_end_to_end_smoke`).
- Bit-for-bit identical image bytes, hash-locked transitive Python packages, or any answer-quality claim.

## Job story

When I want the answer service to run the same way here and later on the QA server, I want one command to build a packaged copy of it and one command each to start, check, and stop that copy, so I never have to set up Python or Docker by hand.

## Acceptance Scenarios

### 1. Build when everything is ready

Given Docker Desktop is open, `--local-rag-status` reports `OK` for Search model, Vector store, and Knowledge release, and the tracked files the image copies have no uncommitted changes · When the owner runs `./scripts/init.sh --container-build` · Then it prints `Checking what the image needs...`, that the first build can take 10 to 30 minutes and downloads the pinned base image and Python packages but no model, a `Still building (<n> minutes so far)...` line each minute, then the image name `manijero-backend:<release-id>-<commit12>`, the knowledge release id, the approximate size, and `Result: the image manijero-backend:<release-id>-<commit12> was built with knowledge release <release-id>.`, exit `0`. Build output is only in the printed log. The image also carries the tag `manijero-backend:local`.

### 2. Build when the image is already up to date

Given an image with the same commit and release already exists · When build runs · Then it builds nothing, points `manijero-backend:local` at it, and ends `Result: nothing new was built; manijero-backend:<tag> is already up to date.`, exit `0`.

### 3. Build or start while a prerequisite is missing

Given any of: Docker Desktop not installed (`Install Docker Desktop from https://www.docker.com/products/docker-desktop/, open it once, then run this command again.`), Docker Desktop not open or still starting (`Open the Docker Desktop app, wait until it says it is running, then run this command again.`), local setup never run, an image part not `OK` (the same plain line `--local-rag-status` prints, naming its fix), uncommitted changes in copied files (build only; names `a developer must save or undo the changes`), an invalid base-image pin (build only; developer fix), or another container command running · When build or start runs · Then before building, creating, or writing anything it prints each matching line, then `Result: the image was not built. <first fix>` or `Result: the answer service in the container did not start. <first fix>`, exit `1`. No model is ever downloaded.

### 4. Build fails or is interrupted

Given `docker build` exits non-zero or the owner presses Ctrl+C · Then no tag is moved, it prints one plain sentence (for a failure: check Docker Desktop has free disk space in its settings and send the log if it repeats), the log path, and `Result: the image was not built. ...`, exit `1`. A running container is left untouched.

### 5. Start when everything is ready

Given `manijero-backend:local` exists, its release equals the currently published local release and its campaign equals the settings file, Ollama runs with the pinned drafting model and digest, port 8000 is free, and no Manijero container exists · When the owner runs `./scripts/init.sh --container-start` · Then it starts the container in the background, waits until `/health` answers as `manijero-backend` and `/ready` answers ready, prints the image tag, release id, the Desktop address `http://127.0.0.1:8000`, the Android emulator address `http://10.0.2.2:8000` with the default-address note, the next steps, and `Result: the answer service in the container started at http://127.0.0.1:8000.`, exit `0`. Closing Terminal does not stop it.

### 6. Start blocked by the image or the port

Given no `manijero-backend:local` image (`Run ./scripts/init.sh --container-build first.`), an image holding an older release or another campaign (`Run ./scripts/init.sh --container-build to package the current knowledge.`), Ollama closed or the drafting model missing or different (the `--local-rag-status` drafting line), port 8000 answered by the mock (`--mock-stop`), by the `--local-rag-start` service (`--local-rag-stop`), by another `manijero-backend` (Ctrl+C in the `--backend` window), or by another program, or a container named `manijero-backend` that Manijero did not create · When start runs · Then it names the one step, creates nothing, touches no other container, exits `1`.

### 7. Start while already running, or after an unclean end

Given the Manijero container is running · When start runs · Then it starts nothing, prints the status lines, and ends `Result: nothing new was started; the answer service in the container is already running at http://127.0.0.1:8000.` (exit `0`), or `... but a check needs attention: do the first step shown above.` (exit `1`). Given a stopped Manijero container left behind · Then it is removed with `An earlier answer service container ended without being stopped; it was cleared.` and start continues.

### 8. Start fails after the container was created

Given the container exits, `/health` does not answer within 120 seconds, `/ready` answers unavailable, or Ctrl+C · Then it saves the container output to the log, removes the container, prints one plain sentence and the log path, and `Result: the answer service in the container did not start. ...`, exit `1`.

### 9. Status

Given the container runs · When the owner runs `./scripts/init.sh --container-status` · Then it prints `OK  Container` (image tag, release, commit, start time in UTC), `OK  Answers` (`/ready` ready), `OK  Search` (image release is still the published release), `OK  Drafting` (host Ollama lists the pinned model and digest, and from inside the container the relay reaches it), the two addresses, and `Result: the answer service in the container is running at http://127.0.0.1:8000.`, exit `0`. Any failing check starts `PROBLEM` with its meaning and first step (Ollama closed: answers continue without the drafting model until Ollama is opened; newer release: build, then stop and start), the addresses still print, and the result says a check needs attention, exit `1`. Given no container or Docker Desktop closed · Then it makes no service probe and ends `Result: the answer service in the container is not running. Start it with ./scripts/init.sh --container-start.` (Docker closed adds that Docker Desktop is not open), exit `1`.

### 10. Stop

Given the Manijero container runs · When the owner runs `./scripts/init.sh --container-stop` · Then it stops it politely (up to 10 seconds), saves its output to a log, removes it, and prints `Result: the answer service in the container has stopped.`, exit `0`. Given none (or Docker Desktop closed) · Then `Result: the answer service in the container was not running, so there was nothing to stop.`, exit `0`. A container without the Manijero label is never stopped or removed. Ollama, Docker Desktop, and images stay as they are.

### 11. Misuse

Given an extra argument after any of the four commands, or a `MANIJERO_LOCAL_RAG_PORT` that is not 1–65535 · Then one plain sentence, no change, exit `2`.

### 12. Safety and privacy

Given any run · Then the published port binds only host `127.0.0.1`; the container runs as a non-root user in the default profile, without reload or access log, and receives only `MANIJERO_ACTIVE_CAMPAIGN` from the host; inside it the service still drafts only through `http://127.0.0.1:11434`, and the relay forwards that port only to the fixed `host.docker.internal:11434`; the image holds no settings file, `.env`, token, test, virtualenv, or file outside the allowlist; build copies only pin-verified artifacts from the local home; no output, label, or log line written by the commands contains a question, passage text, land data, or token.

## Technical approach

- **Commands.** `scripts/init.sh` adds an early `--container-*` dispatch beside the `--local-rag-*` blocks (before Android/Java/`local.properties`), with the same misuse check, port validation, and dev-environment rule (no dev env: build/start/status print the "not set up yet" pair, exit `1`; stop prints the nothing-to-stop result, exit `0`). Each runs `backend/.venv/bin/python backend/scripts/local_rag.py container-build|container-start|container-status|container-stop`; `usage` and the `--check` listing gain the four commands.
- **Operator module.** New `backend/app/local_container.py`: stdlib-only, never imported by the service, same style as `local_rag_service.py` (fixed English sentences, injected ports, exit `0`/`1`/`2`). Reuses `local_rag_bootstrap` (`local_paths`, `read_settings`, `load_pins`, `inspect`, `status_lines`, `RunLog`, `OllamaClient`, `find_model`, `GitCheckout`) and `local_rag_service` (`address_lines`, `answers_check`, `drafting_check`, port-owner check, `LoopbackProbe`, `port_from_environment`). New port `DockerCli` runs `${MANIJERO_DOCKER_CLI:-docker}` (test-only override) with timeouts; tests inject an in-memory fake, subprocess tests a fake executable.
- **Image files** in `backend/container/`: `Dockerfile` (`FROM` the base image pinned by tag and multi-platform index digest in `base-image.json`; non-root user; `pip install` of `backend/requirements-hybrid.txt` constrained by `backend/deploy/requirements-production.txt`, torch from the CPU wheel index; `pip freeze` saved in the image; release and model copied from named build contexts; `current` link; fixed service environment as image `ENV`), `Dockerfile.dockerignore` (allowlist), `entrypoint.py` (starts the relay thread, then runs uvicorn on the container's `0.0.0.0:8000`, no reload, no access log), `ollama_relay.py` (stdlib TCP forwarder: listen `127.0.0.1:11434`, connect `host.docker.internal:11434`, both constants; `--check` probes `/api/tags` through it).
- **Image environment.** Same seven keys as `local_rag_service.launch_environment`, with image paths: release root `/opt/manijero/knowledge-releases`, `MANIJERO_RETRIEVAL_MODE=hybrid`, vector store `…/releases/<id>/vector-store` (owned by the service user), embedding artifact `/opt/manijero/models/bge-m3`, `MANIJERO_GENERATION_PROVIDER=local`, `MANIJERO_LOCAL_MODEL=<record tag>`; `MANIJERO_ACTIVE_CAMPAIGN` comes from the settings file at start.
- **Reproducibility.** Inputs are the git commit, release id, base digest, exact Python pins, and pin-verified artifacts; labels record each (`org.opencontainers.image.revision`, `org.manijero.knowledge-release`, `org.manijero.campaign`, `org.manijero.embedding-revision`, `org.manijero.local-model`, `org.manijero.base-image`, `org.manijero.managed=1`). Build arguments and run arguments are fixed in the appendix.
- **Run.** One container per Mac, name `manijero-backend`, label `org.manijero.managed=1`, `--init`, `--publish 127.0.0.1:<port>:8000`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--restart no`; container commands serialize on `<home>/.container.lock`; logs under `<home>/logs/`.
- **Neighbors.** The "port in use by a `manijero-backend`" sentences in `local_rag_service.py` and the `init.sh` mock block also name `./scripts/init.sh --container-stop`.

## Expected file changes

- `backend/container/Dockerfile`, `Dockerfile.dockerignore`, `base-image.json`, `entrypoint.py`, `ollama_relay.py` — create.
- `backend/app/local_container.py` — create; build/start/status/stop, Docker port, labels, checks.
- `backend/scripts/local_rag.py` — modify; four `container-*` choices and Ctrl+C sentences.
- `backend/app/local_rag_service.py` — modify; port-in-use sentence only.
- `scripts/init.sh` — modify; dispatch, `usage`, `--check` listing, mock port-in-use message.
- `backend/tests/test_local_container.py`, `test_container_image_files.py`, `test_local_container_commands.py` — create (appendix lists); `test_local_rag_service.py` — modify only for the changed sentence.
- `docs/owner-guide.md`, `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`, `docs/constraints/lands.md`, `docs/risks-and-open-questions.md` — update; see below.
- Not changed: `backend/app/main.py`, `ask_api.py`, `local_generation.py`, `retrieval_backend.py`, `knowledge_release.py`, `local_rag_bootstrap.py` (a new public helper only if a private one must be shared), `backend/config/*`, requirements files, `knowledge/*`, `contracts/*`.

## Visual design impact

UI involved: no. No app screen or Spanish app copy changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one bullet: `backend/container/` holds the image definition, entrypoint, and fixed Ollama relay; `local_container.py` is the operator-only builder and launcher in the local-RAG layer; the service code is unchanged inside the image.
- `docs/constraints/operations.md`: update — one MUST: a container command publishes only on host `127.0.0.1`, runs the default profile without reload as a non-root user, passes only the campaign from the host, acts only on containers carrying the Manijero label, and builds only from pin-verified local artifacts with a pinned base digest and no model download; it is not a pilot launcher. Reason: `backend_container_image`.
- `docs/constraints/lands.md`: update — note under the local generation transport rule: owner decision 2026-11-01 (`backend_container_image`): inside the container the constant is unchanged; a fixed relay listening only on the container's `127.0.0.1:11434` forwards to the constant `host.docker.internal:11434` (Ollama on the host Mac), is not configurable, and forwards nowhere else.
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`, `docs/constraints/hosting-and-pilot.md`: not needed — no workflow, domain, UI, wire, or pilot rule change.
- `docs/owner-guide.md`: update — "Install Docker Desktop (one time)", "Build the answer service image", "Start / Check / Stop the answer service in a container" (numbered steps, expected `Result:` line, "if you see something else" table), "Owner walkthrough: container" (appendix steps).
- `backend/README.md`: update — "Container image" subsection: files, build and run arguments, labels, allowlist, relay, exit codes, test-only `MANIJERO_DOCKER_CLI`, honest reproducibility limits.
- `docs/risks-and-open-questions.md`: update — `host.docker.internal` reachability of a loopback-only Ollama is proven only by the walkthrough; images accumulate and are never pruned; transitive packages are not hash-locked; the QA path must reconcile the container with the `serve_pilot.py` rule.
- `PROGRESS.md` "Start and verify" and `docs/progress/known-limitations.md`: one line each at acceptance.

## Focused verification (required)

Offline in the shared `backend/.venv`: no Docker, no Ollama, no model, no `torch`/`chromadb`, no network beyond loopback test sockets, no write outside temporary directories. Subprocess tests set a temporary `MANIJERO_LOCAL_HOME`, an empty `MANIJERO_VENV_ROOT`, a fake `MANIJERO_DOCKER_CLI`, and a free `MANIJERO_LOCAL_RAG_PORT`.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_local_container.py tests/test_container_image_files.py tests/test_local_container_commands.py tests/test_local_rag_service.py tests/test_local_rag_commands.py -q
```
<!-- verify:end -->

The owner walkthrough (real Docker Desktop, real Ollama, real `~/manijero/local`) is run by the owner and recorded by the orchestrator; it is not part of this block.

## Appendix

See [`backend_container_image.appendix.md`](backend_container_image.appendix.md) for research, planner decisions, the fixed build and run arguments, plan, evidence, and the validator checklist.
