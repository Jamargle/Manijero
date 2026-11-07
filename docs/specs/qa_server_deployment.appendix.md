# qa_server_deployment — appendix

Contract: [`qa_server_deployment.md`](qa_server_deployment.md).

## Repository research

- `backend/scripts/serve_pilot.py` — the pilot launcher: `load_config`, `run_preflight`, refuses non-loopback bind unless `MANIJERO_PILOT_ALLOW_PUBLIC_BIND=1`, prints a config summary, runs uvicorn factory `app.main:create_app` without reload or access log. Not in the image today.
- `backend/app/pilot_ops.py` — `run_preflight` adds `evaluate_pilot_review` blockers (committed record is `pending` → `privacy_review_pending` etc.); `run_smoke` checks `/health`, `/ready`, synthetic `/ask` with a token, accepts https or loopback http.
- `backend/app/privacy_review.py` — `evaluate_pilot_review`, Gemini gate (calls the pilot gate), `_section_blockers`; status `pending` yields several blockers (undated, qualification, scope, evidence), so the override must key on `status == "pending"`, not on the blocker list.
- `backend/app/local_generation.py:506` — local drafting blocked in pilot unless the pilot review passed; `resolve_startup_generation(pilot=...)` called from `main.py:129`.
- `backend/app/pilot_config.py` — pilot needs campaign and `MANIJERO_PILOT_CLIENTS_FILE`; refuses a clients file with group/other bits (`clients_permissions`).
- `backend/container/{Dockerfile,Dockerfile.dockerignore,entrypoint.py,ollama_relay.py}` — default-profile entrypoint on `0.0.0.0:8000` with relay; allowlist excludes `backend/scripts/`.
- `backend/app/local_container.py` — `DockerCli` port, `SystemDockerCli`, `container_lock`, `image_info`/`_labels`, `run_argv`, log saving, label `org.manijero.managed`; acts only on name `manijero-backend`.
- `backend/app/environment_profiles.py` — QA settings reader (fixed `QA_KEYS`, https URL, placeholder `.invalid`), `credential_paths(home, "qa-test-device")`, `read_token`, `check_credentials`, `Ports`/`Prompter`, status line wording "placeholder until the QA server is chosen".
- `backend/deploy/environments/qa.settings.env.example` — QA template; `MANIJERO_PUBLIC_URL` placeholder.
- `scripts/init.sh:102-177` — early dispatch pattern for `--environments-status`, `--qa-settings-setup`, `--container-*`.
- `androidApp/build.gradle.kts`, `desktopApp/build.gradle.kts`, `scripts/check-environment-build.sh` — QA builds read `qa-address.local` (`MANIJERO_QA_ADDRESS_FILE` override); no change needed.
- `docs/constraints/operations.md`, `hosting-and-pilot.md` — rules this feature amends (owner decision 9).
- `docs/specs/hosting_provider_review.md` — the hosting decision record (Cloudflare Tunnel for an owned-server pilot); gets a QA addendum.
- `docs/specs/client_environment_builds.appendix.md:29,38` — open question "make `MANIJERO_PUBLIC_URL` and `qa-address.local` agree": resolved by deploy writing both.
- Not inspected: Tailscale CLI output on this Mac (not installed); exact `status --json` capability keys must be confirmed by the implementer against current Tailscale docs and then by the walkthrough.

## Planner decisions

- Extra commands `--qa-status` and `--qa-stop`: `operations.md` requires status and stop as named commands, and stop is the only safe way to remove public exposure.
- Container `manijero-qa`, host port `8100` (`MANIJERO_QA_PORT` test-only override), so local `manijero-backend` on 8000 and QA can run side by side.
- Tags: `manijero-backend:qa-current`, `manijero-backend:qa-previous`; update promotes `manijero-backend:local`. The owner builds with the existing `--container-build`; QA serves the release packaged in the image. QA's own release folder stays unused until `qa_knowledge_deployment` (honest limit, recorded in known-limitations).
- Flag `MANIJERO_QA_TEST_DATA_ONLY=yes`, set only in the QA `docker run` argv; never a settings-file key (QA settings keys stay `QA_KEYS`).
- Workers `1`, so the per-process rate limit is the real limit.
- Restart policy `no`: after a Mac restart the owner re-runs `--qa-deploy` (scenario 2). Mac sleep stops QA; recorded as a limit.
- Smoke `/ask` runs on loopback with the QA key read by the command (never printed); the https check is `/health` only. Reaching the Funnel name from the Mac itself does not prove public reach; the phone-browser step does.

## Fixed argv and constants

- `docker run --detach --init --name manijero-qa --label org.manijero.managed=1 --label org.manijero.environment=qa --publish 127.0.0.1:8100:8000 --env MANIJERO_ACTIVE_CAMPAIGN=<QA campaign> --env MANIJERO_DEPLOYMENT_PROFILE=pilot --env MANIJERO_ENVIRONMENT=qa --env MANIJERO_QA_TEST_DATA_ONLY=yes --env MANIJERO_PILOT_CLIENTS_FILE=/run/manijero/pilot-clients.json --mount type=bind,source=<QA home>/credentials/pilot-clients.json,target=/run/manijero/pilot-clients.json,readonly --cap-drop ALL --security-opt no-new-privileges --restart no manijero-backend:qa-current`
- Tailscale (shape to confirm against current docs, keep in one function each): `status --json` (need `BackendState=="Running"`, `Self.DNSName` ending `.ts.net.`, Funnel/HTTPS capability in `Self.CapMap`); `funnel status --json` (find an existing 443 entry; refuse if it targets anything but `http://127.0.0.1:8100`); `funnel --bg --https=443 http://127.0.0.1:8100` on; `funnel --https=443 off` off. CLI lookup: `MANIJERO_TAILSCALE_CLI` (tests), `tailscale` on `PATH`, `/Applications/Tailscale.app/Contents/MacOS/Tailscale`.
- Address: `https://<DNSName without trailing dot>`; written to QA `settings.env` (`MANIJERO_PUBLIC_URL` line replaced atomically, comments kept, mode kept) and `<repo>/qa-address.local` (or `MANIJERO_QA_ADDRESS_FILE`), one line.
- Lock `<QA home>/.qa.lock`; logs `<QA home>/logs/qa-<op>-<UTC>.log`; timeouts reuse `local_container` constants (start 120 s).

## Implementation plan

1. `privacy_review.py`: add `qa_test_data_mode`, `PilotGate`, `pilot_gate`; module docstring notes owner decision 9.
2. `pilot_ops.run_preflight`: use `pilot_gate`; add `qa_test_data_only` to `PreflightReport`.
3. `local_generation.resolve_local_provider`: replace the pilot check with `pilot_gate(...).passed` on `source`.
4. `serve_pilot.py`: warning line (stdout and stderr) and `privacy_review: pending (QA test data only)` summary value; docstring mentions the QA path.
5. `entrypoint.py`: pilot branch (relay, then `serve_pilot.main` with fixed args and the bind acknowledgement in its own environment); default branch unchanged.
6. `Dockerfile`/allowlist: copy `backend/scripts/serve_pilot.py`; add launchers label.
7. `environment_profiles.write_public_url(home, url)` and status wording when the URL is not a placeholder.
8. `qa_deployment.py`: ports (`DockerCli` reuse, `TailscaleCli`, probe, prompter, clock), prerequisite collector, deploy/update/rollback/status/stop, refusal-code → plain-sentence table, auto-restore on failed update/rollback.
9. `backend/scripts/qa_service.py`: argv dispatch, real ports, Ctrl+C sentence.
10. `scripts/init.sh`: dispatch block, `usage`, `--check` listing.
11. Tests (below), then docs per the contract's documentation section, owner guide last.

## Verification plan

- `test_qa_test_data_gate.py`: override passes only for exact pilot+qa+yes with a `pending` record; `rejected`, invalid, unreadable, `QA`, `qa ` , `yes1`, `true`, missing flag, development profile all stay blocked; Gemini gate unchanged; local drafting enabled only in the mode; preflight report flag; launcher prints the warning and still refuses without the mode (subprocess with fake clients file 0600 and temp corpus).
- `test_qa_deployment.py` (in-memory fakes): every prerequisite line of scenario 3 and that nothing changes; first deploy order (tag, run, ready, smoke, Funnel on, address writes); already-running; restart after stop; failure cleanup leaves Funnel off; update promote/no-op/auto-restore; rollback swap/none/failure; status lines; stop order (Funnel off first), foreign container and foreign Funnel entry untouched; no token/question in output or log.
- `test_qa_deployment_commands.py` (subprocess via `init.sh` with fake `docker` and `tailscale` executables, temp homes, non-tty refusal, `yes` piped where a tty is simulated): exit codes `0/1/2`, `Result:` lines, misuse.
- `test_container_image_files.py`: allowlist includes `serve_pilot.py`, label present, entrypoint pilot branch argv and default branch unchanged.
- `test_environment_profiles.py`: `write_public_url` keeps comments/other lines and mode; status wording.

## Evidence to capture

- Focused block result line; `bash -n` result.
- One redacted transcript per command from the fake-CLI subprocess tests (Result lines only).
- Owner walkthrough record: Tailscale setup done, deploy Result, phone browser `/health` at the https address, `/ask` without key → `401`, update Result, rollback Result, stop Result, one missing-prerequisite case (Tailscale closed) and its recovery.

## Feature evidence

- `bash -n scripts/init.sh`: ok.
- `./scripts/init.sh --feature qa_server_deployment`: 404 passed, 1 warning (gate 11, deployment 48, commands 12, plus image files, pilot operations, local generation, environment profiles, local container).
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed (backend-tests 1943 passed, 4 skipped; harness-tests 20 passed).
- Fake-CLI subprocess runs (`test_qa_deployment_commands.py`): misuse exit 2; no Tailscale/Docker/QA setup gives `Result: QA was not deployed|updated|rolled back. ...` exit 1 with nothing created; status with nothing running exit 1; stop with nothing running exit 0.
- Tailscale forms (confirmed against current docs, to be confirmed by the owner walkthrough), all in one block of `app/qa_deployment.py`: `status --json` (`BackendState`, `Self.DNSName`, `Self.CapMap`/`Capabilities` holding `https` and a `funnel` name, or `CertDomains`); `funnel status --json` (`Web`, `AllowFunnel`, `TCP`); `funnel --bg --https=443 http://127.0.0.1:8100`; `funnel --https=443 off`.
- Not run here (owner walkthrough): real Tailscale, Docker Desktop, Ollama, phone browser; clients-file readability inside Docker Desktop; image build with the new `serve_pilot.py` copy.
- Deviations: no new test in `test_environment_profiles.py`/`test_pilot_operations.py` (`write_public_url` and the preflight flag are covered in `test_qa_deployment.py` and `test_qa_test_data_gate.py`); `test_local_rag_service.py` operator list gained `qa_deployment`; `local_container.container_info`/`container_lock` gained optional name/busy arguments and `ImageInfo.image_id`.
## Validator checklist

- Gate: override keyed on exact values and `status == "pending"`; Gemini and non-QA paths byte-for-byte unchanged in behavior; warning printed.
- Container: publish `127.0.0.1` only; non-root; no new env beyond the fixed list; clients file read-only; launcher is `serve_pilot` in pilot; default path unchanged.
- Funnel touched only for its own 443 → `127.0.0.1:8100` entry; stop removes it before stopping the container; no account automation.
- Every command checks prerequisites first, confirms before deploy/update/rollback, ends with one `Result:` line, exits non-zero on failure; failed update/rollback restores the previous version.
- No token, question, answer, or land text in output, logs, labels; agents' tests use fake tokens only.
- Docs: both constraint files, hosting decision addendum, owner guide within budget with the walkthrough named as manual acceptance.

## Handoff

- Status: `accepted` 2026-11-07 after the owner walkthrough (update/rollback not exercised: no newer image). Earlier: `passing`; validator accept with condition `pending owner walkthrough` (2026-11-03); holding commit made. Next: owner walkthrough, then evidence-only acceptance (no second validator).
- Done: gate (`privacy_review.pilot_gate`), launcher warning, image entrypoint/Dockerfile/allowlist, `qa_deployment.py`, `qa_service.py`, `init.sh` dispatch, tests, constraints, hosting addendum, ARCHITECTURE, owner guide, backend README.
- Left for acceptance: owner walkthrough (confirms Tailscale JSON/CLI forms and Docker clients-file access); then `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`, `PROGRESS.md` (Mac sleep, public Funnel hostname, test-data rule, QA serves the image's release until `qa_knowledge_deployment`).
- Needs `--container-build` before a real deploy: the current `local` image lacks the pilot launcher label.
