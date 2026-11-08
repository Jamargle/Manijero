# Show backend health in a plain-language browser dashboard

## Source metadata

- `id`: monitoring_dashboard · `area`: operations · `depends_on`: backend_health_metrics, environment_profiles · `status` at planning: not_started
- User-visible behavior: one owner command starts a free, self-hosted dashboard in Docker Desktop and prints its browser address; the page shows, for local and QA, four checks (service up/down, answer speed, error rate, abstention rate), each as OK / warning / problem with what it means and the first thing to do. Status and stop commands complete the set.
- Verification: static checks of the committed dashboard, provisioning, rules, thresholds, image pins, and privacy denylist, plus command tests against a fake Docker; none needs Docker running. An optional Docker-backed smoke and a short owner walkthrough complete acceptance.
- Notes (owner decisions, verbatim):
  - Free, self-hosted Grafana run with Docker Desktop (already installed on the owner's machine), reading the Prometheus /metrics endpoint from backend_health_metrics (accepted feature; read its spec/archive appendix for metric names).
  - One named command starts it and prints the browser address, for the local and QA environments; QA wiring may use a placeholder until qa_server_deployment.
  - First panels: service up/down, answer speed, error rate, and abstention rate, each shown as plain-language OK / warning / problem with what it means and the first thing to do (see docs/constraints/operations.md).
  - Never show question text, land context, client identifiers or tokens.
  - Acceptance: validator accept plus a short owner walkthrough (run one command, open one address, check it reads clearly). The validator may accept with condition "pending owner walkthrough".
- Planning decisions: Grafana cannot read `/metrics` by itself, so a pinned Prometheus container scrapes it and Grafana reads Prometheus; both are free and self-hosted. Monitoring has its own start/status/stop commands (owner decision "one named command starts it"); it does not start with `--local-rag-start` or `--container-start`, which keep working without Docker (see Durable documentation). Dashboard copy is English, like every existing owner command and `docs/owner-guide/monitoring.md`. Files read by Prometheus or Grafana as YAML are written as JSON documents (valid YAML) so stdlib `json` can check them without a new dependency.

## Goal

Let the owner see, in one browser page and without reading numbers or logs, whether the local and QA answer services are up and answering well, and what to do first when they are not.

## Non-goals

- No alerting, notifications, or outage detection claim (`qa_service_alerts`); the dashboard runs on the owner's Mac and is not alerting.
- No QA deployment, real QA address, or live QA scrape evidence (`qa_server_deployment`); QA shows "not set up yet" until a real address exists.
- No change to `GET /metrics`, the answer service, the apps, `contracts/openapi.yaml`, or the existing service and container commands.
- No panels beyond the four checks per environment (no generation, release, source-update, or rate-limit panels); no raw charts as the primary view.
- No Grafana accounts, logins, editing, Explore, alerting, plugins, or prod monitoring.

## Job story

When I want to know whether Manijero is working, I want to run one command and open one address that tells me in plain words what is OK, what needs attention, and what to do first, so I can look after the service without terminal or monitoring skills.

## Acceptance Scenarios

### 1. One command starts the dashboard and prints its address
Given Docker Desktop is open · When the owner runs `./scripts/init.sh --monitoring-start` · Then it pulls only the pinned images (by digest), starts a Prometheus and a Grafana container labelled `org.manijero.managed=1`, publishes only Grafana and only on `127.0.0.1:3000`, waits until Grafana is healthy, prints `Open http://127.0.0.1:3000 in your web browser.`, and ends with one `Result:` line. Re-running while it runs reports the address and changes nothing.

### 2. Missing prerequisites stop early with one fix
Given Docker Desktop is not installed, not open, the pins file is invalid, or port 3000 is used by something else · When the start runs · Then nothing is created, one plain sentence names the problem and its single fix (Docker sentences reuse `local_container`'s), the `Result:` line says the dashboard did not start, and the exit code is `1`. A container with a monitoring name but without the Manijero label is never touched.

### 3. Status and stop
`--monitoring-status` says running with the address, or not running with the start command (exit `0`/`1`). `--monitoring-stop` stops and removes only the labelled monitoring containers, keeps the history volume, and reports "nothing to stop" when none run. Both stay read-only or idempotent like the container commands.

### 4. The page shows four plain-language checks per environment
Given the dashboard is open · Then it shows a "Local" row and a "QA" row, each with the four checks below, and a short "How to read this page" note. Each check shows one sentence: the state word (`OK`, `Warning`, `Problem`, or a neutral `Not enough data` / `Not set up yet`), what it means, and the first thing to do, coloured green / amber / red / grey. Before the first scrape or when data is missing it shows a fixed "No information yet" sentence naming `--monitoring-status`. Nothing requires reading a chart.

| Check (rule) | Window | OK | Warning | Problem | Neutral |
|---|---|---|---|---|---|
| Service (`manijero:status_service`) | now, 5 min | reachable and `manijero_ready` 1 | ready now, but unreachable or not ready at some point in 5 min | unreachable (`up` 0), or reachable but `manijero_ready` 0 (separate sentences) | QA without a real address: `Not set up yet` |
| Answer speed (`manijero:status_speed`) | 15 min | p90 `/ask` time < 10 s | 10–30 s | ≥ 30 s | no `/ask` in window |
| Error rate (`manijero:status_errors`) | 15 min | 5xx share of `/ask` < 2 % | 2–10 % | ≥ 10 % | no `/ask` in window |
| Abstention rate (`manijero:status_abstentions`) | 1 h | `abstained` share of answers < 50 % | 50–80 % | ≥ 80 % | fewer than 5 answers |

Thresholds live once in `backend/monitoring/thresholds.json`; the rules and panel texts must match it (checked statically). The abstention text says a high share can be correct when questions fall outside the covered topics.

### 5. Local and QA targets
Given the local service or container runs on `127.0.0.1:<port>` (`MANIJERO_LOCAL_RAG_PORT`, default 8000) · Then Prometheus scrapes `host.docker.internal:<port>/metrics` as `env="local"` every 15 s. Given the QA settings file has a non-placeholder `MANIJERO_PUBLIC_URL` and complete QA credentials (`environment_profiles.check_credentials`) · Then a `env="qa"` job scrapes `<url>/metrics` every 30 s with the QA client token through a read-only mounted `credentials_file`; otherwise no QA job exists and the QA row shows `Not set up yet` with "Nothing to do until the QA service is deployed." The token never appears in argv, generated config, output, or logs.

### 6. Privacy and pinning hold
Then: Prometheus keeps only `manijero_*` and `up` series and only allowlisted labels (the `backend_health_metrics` allowlist plus `env`, `job`, `instance`); no committed or generated file, panel, rule, or command output contains question or answer text, land context, names, notes, client ids, or token values; Grafana runs with anonymous Viewer only, login form, Explore, editing, plugin downloads, analytics, and update checks off; both images are named as `tag@sha256:<64 hex>` in a reviewed pins file.

## Technical approach

- New `backend/app/local_monitoring.py` (stdlib only) owns start/status/stop, mirroring `local_container.py`: reuse its `DockerCli` port, `docker_state`, Docker sentences, `MANAGED_LABEL`, and the `MANIJERO_DOCKER_CLI` test seam; plain sentences, one `Result:` line, log file under `<local home>/logs/`, lock file, exit codes 0/1/2.
- Containers via fixed `docker` argv (no compose): network `manijero-monitoring`; `manijero-prometheus` (unpublished, config dir mounted read-only, named volume `manijero-monitoring-data`, retention 15 days); `manijero-grafana` (`-p 127.0.0.1:3000:3000`, provisioning and dashboard mounted read-only, no volume). Both carry `org.manijero.managed=1` and `org.manijero.component=monitoring`, run with only fixed `-e` values, no inherited environment.
- Grafana admin password: random per start, passed by `-e NAME` from the child process environment (never argv), never written or printed; login form off, anonymous Viewer on.
- Runtime `prometheus.yml` (JSON) is generated into `<local home>/monitoring/` at start: local job, optional QA job, `metric_relabel_configs` keep/labelkeep, `rule_files` pointing at the committed rules. Committed under `backend/monitoring/`: `images.json`, `thresholds.json`, `prometheus/rules.json`, `grafana/provisioning/datasources/manijero.yaml`, `grafana/provisioning/dashboards/manijero.yaml`, `grafana/dashboards/manijero-health.json`.
- Panels are Grafana stat panels over the four recording rules, with value mappings carrying each state's full sentence and colour, plus a "No data" mapping. Rule codes: `-1` neutral, `0` OK, `1` warning, `2`/`3` problem variants, `4` not set up (QA via `absent(up{env="qa"})`).
- New entry script `backend/scripts/monitoring.py`; `scripts/init.sh` dispatches `--monitoring-start|--monitoring-status|--monitoring-stop` like the `--container-*` block and lists them in `usage`.

## Expected file changes

- `backend/app/local_monitoring.py`, `backend/scripts/monitoring.py` — create.
- `backend/monitoring/` (files above) — create.
- `scripts/init.sh` — modify; dispatch block and usage lines.
- `backend/tests/test_monitoring_files.py`, `backend/tests/test_local_monitoring.py`, `backend/tests/test_local_monitoring_commands.py`, `backend/tests/test_monitoring_docker_smoke.py` — create.
- Docs listed below.

## Visual design impact

App UI involved: no. The Grafana page is owner-facing: plain sentences, never colour alone (state word always in the text), readable at browser zoom 200 %.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one line: owner-run monitoring (Prometheus + Grafana in Docker Desktop) reads `/metrics`; files in `backend/monitoring/`.
- `docs/constraints/operations.md`: update — amend the first Monitoring MUST with the owner decision (2026-11-02) that monitoring has its own start/status/stop commands, and add one MUST: monitoring publishes only `127.0.0.1`, uses digest-pinned images, keeps only `manijero_*`/`up` series and allowlisted labels. Reason: this spec.
- `docs/owner-guide/monitoring.md`: update — "Open the health dashboard" (start, check, stop, the state table, two "if it differs" rows) and "Owner walkthrough: health dashboard"; at most 60 lines.
- `backend/README.md`: update — "Health dashboard" section, at most 30 lines.
- `docs/progress/known-limitations.md`: update — one line: runs only on the owner's Mac, not alerting, QA not set up until `qa_server_deployment`, thresholds are initial.
- `AGENTS.md`, `CONSTRAINTS.md` index, `DESIGN.md`, `contracts/`: not needed.

## Focused verification (required)

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_monitoring_files.py tests/test_local_monitoring.py tests/test_local_monitoring_commands.py tests/test_monitoring_docker_smoke.py tests/test_local_container.py tests/test_local_container_commands.py -q
```
<!-- verify:end -->

`test_monitoring_docker_smoke.py` skips unless `MANIJERO_MONITORING_DOCKER_SMOKE=1` (it then needs Docker Desktop open). Owner walkthrough: run `./scripts/init.sh --monitoring-start`, open the printed address, confirm the Local row reads clearly with the local service stopped and then started, run `--monitoring-stop`.

## Appendix

See [`monitoring_dashboard.appendix.md`](monitoring_dashboard.appendix.md) for research, plan, evidence, and the validator checklist.
