# monitoring_dashboard — appendix

## Repository research

### Files inspected

- `docs/constraints/operations.md` — Owner operability and Monitoring MUSTs this feature must satisfy (one command, plain `Result:` line, loopback only, pinned downloads, no private data).
- `docs/specs/backend_health_metrics.md` — metric families, label allowlist, buckets (10 s and 30 s exist, so the speed thresholds fall on bucket edges), `development` open / `pilot` token gate, per-process reset.
- `backend/app/health_metrics.py` — exact names: `manijero_ready`, `manijero_http_requests_total{route,code}`, `manijero_request_duration_seconds{route}`, `manijero_answers_total{status}` (`answered`, `abstained`, `needs_land_clarification`), `manijero_abstentions_total{reason}`.
- `backend/app/local_container.py` — `DockerCli` protocol, `docker_state`, Docker missing/closed sentences, `MANAGED_LABEL`, `MANIJERO_DOCKER_CLI`, timeouts, lock and log naming to mirror.
- `backend/container/base-image.json` — reviewed pin shape (`image`, `digest`, `reviewed_on`, `reason`) to copy for `images.json`.
- `backend/scripts/local_rag.py` — entry-script shape: argparse command, Ctrl+C and failure wording table, log-file fallback.
- `scripts/init.sh` lines 99–177 — owner-command dispatch blocks (`Run %s on its own`, venv check, `MANIJERO_LOCAL_RAG_PORT` validation) and `usage`.
- `backend/app/environment_profiles.py` — `qa_home()`, `read_profile_settings("qa")`, `ProfileSettings.placeholder_url` (`.invalid` host), `credential_paths(home, "qa-test-device")`, `check_credentials` (reads only; never read the token content in planning).
- `backend/tests/test_local_container_commands.py` — fake Docker shell script recording calls, `run_init` with temp `MANIJERO_LOCAL_HOME`; reuse for command tests.
- `backend/requirements-dev.txt` — only `pytest` and `jsonschema` beyond runtime deps; no YAML parser, hence JSON-as-YAML config.
- `ARCHITECTURE.md`, `docs/owner-guide.md` headings, `PROGRESS.md` Current state — where docs land; owner copy is English.

Not inspected: Grafana/Prometheus upstream docs and registries (no network in planning); `local_rag_service.py` internals.

### Existing patterns to follow

- Owner commands: plain sentences, one `Result:` line, log path on unexpected error, exit 0/1/2, idempotent re-runs, act only on `org.manijero.managed=1`.
- Reviewed pins: tag plus multi-platform index digest read from the registry's anonymous manifest API, `reviewed_on`, one-sentence `reason`.
- Test seams through environment variables marked "tests only" (`MANIJERO_DOCKER_CLI`, `MANIJERO_LOCAL_HOME`, `MANIJERO_QA_HOME`); add `MANIJERO_MONITORING_PORT` (tests and developers only) mirroring `MANIJERO_LOCAL_RAG_PORT`.

### Current gaps and risks

- `host.docker.internal` reaching a service bound to host `127.0.0.1` relies on Docker Desktop for Mac forwarding; confirm in the optional smoke and owner walkthrough. If it fails, record it and stop; do not rebind the service off loopback.
- QA token mount: the token file is `0600`; Prometheus runs as `nobody` in its image. If a bind-mounted `0600` file is unreadable in the container, copy it at start into `<local home>/monitoring/qa-token` (`0600`) and run Prometheus with `--user` matching the host uid; never print or log it. Live QA scraping is unverified until `qa_server_deployment`.
- Initial thresholds are planner choices (speed vs. local drafting latency is unmeasured as a p90); cross-check the measured numbers in the `local_generation_provider` appendix (archive) and, if the 10 s OK bound is clearly wrong for local drafting, change `thresholds.json` with a reason line in evidence.
- Image sizes for the first pull are unknown; measure and print an approximate size on first start.

## Implementation plan

1. Write `backend/monitoring/images.json` with current stable `grafana/grafana-oss` and `prom/prometheus` tags and their index digests; record the lookup in evidence.
2. Write `thresholds.json` (check, window, bounds, minimum volume) matching the contract table.
3. Write `prometheus/rules.json`: one group, four recording rules per contract codes, labelled by `env`, using `increase`/`histogram_quantile` (counter resets handled).
4. Write Grafana provisioning (datasource `http://manijero-prometheus:9090`, uid fixed; dashboard provider, `allowUiUpdates: false`) and `manijero-health.json`: text note, Local and QA rows, four stat panels each, value mappings with full sentences and colours, "No data" mapping.
5. `local_monitoring.py`: prerequisites (Docker state, pins valid, port free or ours, foreign-container check), config generation (local job, optional QA job from QA settings + credentials check), pull by digest, network, run both containers, wait for `GET /api/health`, status, stop.
6. `backend/scripts/monitoring.py` and the `scripts/init.sh` dispatch block plus `usage` lines.
7. Tests (below), then docs per the contract, then evidence.

## Verification plan

- `test_monitoring_files.py` (no Docker): every JSON parses; pins match `^[a-z0-9./-]+:[A-Za-z0-9._-]+$` plus `sha256:[0-9a-f]{64}`; rule thresholds and panel mapping texts match `thresholds.json`; every panel targets only `manijero:status_*`; every rule reads only `manijero_*` and `up`; every label used is allowlisted; each state code has a mapping with a state word, meaning, and first step; a denylist (`question`, `answer_text`, `land`, `client_id`, `token`, `notes`, `name=`, `passage`) finds nothing in expressions and labels; Grafana settings disable login form, Explore, analytics, update checks, plugin preinstall.
- `test_local_monitoring.py` (fake ports): generated `prometheus.yml` for local-only, placeholder QA, and real-QA temp homes (fake token, `MANIJERO_QA_HOME`); argv publishes only `127.0.0.1:3000`, uses `@sha256:` references, carries both labels, never contains the fake token or password; foreign container untouched; re-start idempotent; stop removes only labelled containers and keeps the volume.
- `test_local_monitoring_commands.py`: `./scripts/init.sh --monitoring-start|status|stop` with the fake Docker script, Docker missing/closed, port busy, extra argument (exit 2), and `--help` lists the three commands; output ends with one `Result:` line and never prints the fake token.
- `test_monitoring_docker_smoke.py` (skipped unless `MANIJERO_MONITORING_DOCKER_SMOKE=1`): `promtool check config` and `check rules` in the pinned image, real start, Grafana health and dashboard reachable anonymously, stop.
- Run the focused block; run `./scripts/init.sh --backend-tests` once as evidence.

## Evidence to capture

- Image tags, digests, and the date and method of lookup.
- Focused block result line; full backend suite result line.
- Optional smoke result on the owner's Mac (or "not run" with reason).
- Owner walkthrough outcome, or "pending owner walkthrough".

## Feature evidence

Implementer session 2026-11-02 (offline: no network, Docker not usable from the session).

- Focused block (`./scripts/init.sh --backend-tests tests/test_monitoring_files.py tests/test_local_monitoring.py tests/test_local_monitoring_commands.py tests/test_monitoring_docker_smoke.py tests/test_local_container.py tests/test_local_container_commands.py -q`): `132 passed, 2 skipped` (the smoke skips without opt-in; `test_image_pins_carry_digests` skips while digests are null).
- `./scripts/init.sh --fast`: all 10 checks passed; `backend-tests 1925 passed, 6 skipped`. One earlier failure (`test_the_service_never_imports_the_operator_modules`) was fixed by adding `local_monitoring` to its operator list.
- Image pins: NOT digest-pinned. No network in the session, so digests were not read; `images.json` pins explicit tags `grafana/grafana-oss:12.0.0` and `prom/prometheus:v3.4.0` with `"digest": null` (start pulls by tag). The loader and static test accept a valid digest or null; a developer fills the digests with `docker buildx imagetools inspect` (backend/README.md, Health dashboard). Tag existence was not checked against the registry.
- Docker smoke: not run (Docker and network unavailable); `promtool` checks of the rules and `prometheus.yml`, the PromQL itself, `host.docker.internal` reaching the loopback service, the QA token mount, and the Grafana provisioning are therefore unverified.
- Deviation from the plan: `rules.json` has six helper recording rules (`manijero:ask_*`, `manijero:answers_1h`, `manijero:abstention_percent_1h`) before the four `manijero:status_*` rules, in one group; panels target only the status rules. Grafana settings live as `GRAFANA_SETTINGS` in `local_monitoring.py` (environment variables), not in a file.
- Owner walkthrough (2026-11-03): passed on the owner's Mac; all 6 steps as expected. First start about 30 s; stop and status printed the documented `Result:` lines. Thresholds and English text not explicitly confirmed (kept as built). See the acceptance record.

## Validator checklist

- [ ] Focused block passes without Docker running; smoke skips cleanly when not opted in.
- [ ] Commands follow operations.md owner operability (one command, prerequisite sentences, `Result:` line, exit codes, idempotent).
- [ ] Only `127.0.0.1` is published; images are digest-pinned; only labelled containers are stopped or removed.
- [ ] Every panel shows a state word, meaning, and first step for each code, and a "No data" sentence; thresholds match `thresholds.json`.
- [ ] QA is `Not set up yet` with the placeholder address; the token is never in argv, files under the repo, output, or logs.
- [ ] Prometheus keeps only `manijero_*`/`up` and allowlisted labels; denylist test passes.
- [ ] No new Python, Gradle, or app dependencies; no app, `/metrics`, or contract changes.
- [ ] Docs updated per the contract within size budgets; `operations.md` amendment cites the owner decision.
- [ ] Acceptance condition: owner walkthrough done, or accept recorded as "pending owner walkthrough".

## Handoff

- Status: `accepted`; validator accept plus owner walkthrough passed 2026-11-03 (docs/validations/monitoring_dashboard.md).
- Next: none for this feature.
- Last checks: focused block 132 passed, 2 skipped (Docker smoke, digest); `--fast` all 10 passed.
- Open: image digests are null (tags `grafana/grafana-oss:12.0.0`, `prom/prometheus:v3.4.0` unverified against the registry); the owner should confirm thresholds and English dashboard text.
