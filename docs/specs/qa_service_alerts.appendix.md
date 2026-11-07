# qa_service_alerts — appendix

## Repository research

### Files inspected

- `docs/constraints/operations.md` — owner operability MUSTs; Monitoring MUSTs: "check outside the host" (needs the owner-decision amendment), no private data in alerts, alert on an owner-chosen channel, never the same unresolved problem more than once per hour.
- `docs/specs/qa_server_deployment.md` — QA container `manijero-qa` on `127.0.0.1:8100`, QA labels, Funnel 443 entry, `--qa-stop` turns Funnel off then removes the container, `--restart no` (a crash leaves an exited container).
- `backend/app/qa_deployment.py` — reusable: `CONTAINER_NAME`, `LABEL_ENVIRONMENT`, `_is_ours`, `_qa_container`, `_read_tailscale` (`state`, `funnel` = `ours`), `_lock_path` / `LOCK_NAME` (`.qa.lock` in QA home), `port_from_environment`, `SystemTailscaleCli`, `system_public_probe` (https `/health`, service name check), `QaPorts` shape.
- `backend/app/local_container.py` — `DockerCli`, `docker_state` (`missing`/`closed`/`ready`), `container_info`, `container_lock` (non-blocking `flock`), `SystemDockerCli` resolves `docker` with `shutil.which` (launchd PATH must include Docker's bin).
- `backend/app/environment_profiles.py` — `qa_home()` (`MANIJERO_QA_HOME` tests only), `read_profile_settings(QA)` → `public_url`, `credential_paths(home, QA_CLIENT_ID)`, `check_credentials`, `read_token`, file-mode constants.
- `backend/app/local_monitoring.py` — `qa_target` pattern for "real QA address + complete keys"; token only via file, never argv.
- `backend/monitoring/thresholds.json`, `backend/monitoring/prometheus/rules.json` — `errors.window` `15m`, `warning_percent` 2, `problem_percent` 10; dashboard error share = 5xx of `/ask` over `/ask`, only when `/ask` count > 0.
- `backend/app/health_metrics.py` — `manijero_http_requests_total{route,code}` counter since process start; `manijero_ready`.
- `scripts/init.sh` lines 202–248 — dispatch blocks for `--monitoring-*` and `--qa-*` (`Run %s on its own`, venv check, exec entry script); usage lines 381–400.
- `docs/owner-guide.md` "Set up Tailscale (one time)", "Deploy, update, roll back, check, and stop QA", "Owner walkthrough: QA" — tone and table shape to copy.
- `backend/tests/test_local_rag_service.py` — `test_the_service_never_imports_the_operator_modules` list to extend.
- `docs/specs/monitoring_dashboard.md` + appendix — owner-command and English-copy conventions; dashboard explicitly "not alerting".

Not inspected: Telegram Bot API docs and launchd man pages (no network in planning; behavior below is from general knowledge and must be confirmed by the implementer against fakes and in the owner walkthrough); `backend/scripts/qa_service.py` internals; existing test fakes beyond names.

### Planner decisions

1. `--qa-alerts-setup` exists because operations.md forbids hand-editing settings; it automates only storing the token and reading the chat id, not account or bot creation.
2. Secrets path `~/manijero/alerts/credentials/telegram.json`: outside the checkout and under the existing "agents never read `~/manijero/*/credentials/`" rule.
3. Erroring uses the dashboard's Problem level (≥ 10 % over 15 min); Warning (2 %) would page on single errors at QA's low traffic. Thresholds are read from `thresholds.json`, never copied.
4. Debounce of 2 checks (≈5–10 min) avoids alerts during `--qa-update` container swaps and blips; plus the QA lock skip.
5. Reminder 4 h (owner: "every few hours"); 60-minute same-kind cap satisfies operations.md.
6. "Stopped on purpose" = exactly what `--qa-stop` leaves, so stopping QA does not page; Docker closed cannot be told apart and does page.
7. Public probe only when local `/health` passes, so a down container gives one alert, not two.
8. No `ts.net` address in messages (may contain the Mac or owner name). English copy, consistent with owner commands.

### Current gaps and risks

- launchd gives agents a minimal PATH: the plist sets `PATH=/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin`; Tailscale has the app-bundle fallback. Confirm in the walkthrough.
- macOS privacy (TCC) can block a launchd python reading a repo under `~/Documents`/`~/Desktop`; status must show "no check has run yet" plainly. Ventura+ shows a "Background item added" notice.
- The public probe from the same Mac may resolve the `ts.net` name over the tailnet, so it proves Funnel/serve answers, not reachability from the internet (known limitation).
- The plist pins the checkout path at start; a moved checkout breaks the job — status reports the plist path mismatch and says to run start again.
- Telegram embeds the token in the request URL: never log URLs, never include exception `repr`; map failures to fixed codes (`token_rejected`, `chat_unavailable`, `unreachable`).
- `getUpdates` returns sender names: read only `chat.id` of `chat.type == "private"`, never store or print anything else.

## Implementation plan

1. Expose public aliases in `qa_deployment.py` (`is_qa_container`, `qa_container`, `read_tailscale`, `lock_path`) without behavior change.
2. `qa_alerts.py` paths and seams: alerts home, credentials file (0700/0600), `state.json`, `logs/qa-alerts.log` (one line per check, UTC time + codes, roll at 1 MB keeping one old file).
3. Telegram port: `get_me`, `latest_private_chat`, `send(text)`; real HTTPS transport plus loopback-only `MANIJERO_TELEGRAM_API` seam; fixed failure codes.
4. Probe step: Docker state, QA container, loopback `/health` `/ready`, `/metrics` parse of `/ask` totals and 5xx (with token header), Funnel state, public probe; returns one observation record.
5. Classifier and state machine (pure functions over observation, previous state, clock, thresholds): counter samples kept ~25 min, reset on drop; debounce, alert, reminder, cap, recovery, stopped-on-purpose, lock skip.
6. Messages: fixed template table from contract scenario 5; local `HH:MM`.
7. Commands: setup (getpass, 3 tries for the chat), test, start (prerequisites, plistlib file, `launchctl bootstrap gui/<uid> <plist>`; reload when content differs), stop (`bootout gui/<uid>/org.manijero.qa-alerts`, remove file), status (`launchctl print gui/<uid>/org.manijero.qa-alerts` return code, state file), check.
8. `backend/scripts/qa_alerts.py` entry (argparse, misuse exit 2, unexpected error → log path) and `scripts/init.sh` dispatch + usage.
9. Tests, then docs per the contract, then evidence.

## Verification plan

- `test_qa_alerts.py` (in-process fakes, fake clock): each kind is classified from fake probes; down beats not ready beats erroring; public checked only when `/health` passes; stopped-on-purpose is quiet and closes an alerted incident; lock held → skipped, state unchanged; erroring uses `thresholds.json` (patching the file changes the result), needs a full window, ignores zero `/ask`, resets on counter drop; one alert after 2 bad checks, none after 1; reminder at 4 h not 3 h 59; same kind not re-sent within 60 min after a flap; kind change sends one message; recovery after 2 OK checks only when an alert was sent; failed send retried next check; corrupt state starts fresh; messages, log, and state never contain the fake token, chat id, `ts.net` address, or client id.
- `test_qa_alerts_commands.py` (subprocess through `./scripts/init.sh`, fake launchctl script recording argv, fake Docker/Tailscale scripts, loopback fake Telegram): setup writes 0600 file and prints no value, rejects bad tokens, asks before replacing, refuses without TTY; test alert success and each failure sentence; start refuses each missing prerequisite before writing, writes the plist (label, interval 300, RunAtLoad, absolute paths, PATH, no secret or `MANIJERO_*`), is idempotent; stop and nothing-to-stop; status lines and exit codes, stale last check wording; extra argument exit 2; `--help` lists the five commands; no output ends without one `Result:` line; launchctl argv only ever names `org.manijero.qa-alerts`; no real `launchctl` or network is touched.
- `test_qa_deployment.py` still passes (aliases only); `test_local_rag_service.py` operator list includes `qa_alerts`.
- Run the focused block, then `./scripts/init.sh --fast` once as evidence.

## Evidence to capture

- Focused block result line; `--fast` result line.
- Confirmation that no test calls real `launchctl`, Telegram, or network (how it is guarded).
- Owner walkthrough outcome (bot set up, job started, test alert received), or "pending owner walkthrough".

## Feature evidence

Implementer session 2026-11-07.

- Focused block check: it runs unchanged and offline (`bash -n scripts/init.sh`, then `--backend-tests` with the four files). No mechanical fix needed. The worktree had no `backend/.venv` link; `./scripts/init.sh --setup-python` linked the shared environment (no install). The `MANIJERO_PYTHON` default in the block points at that link; `pytest_python` falls back to `python3` when it is absent.
- `./scripts/init.sh --feature qa_service_alerts`: `195 passed in 10.54s` (63 in `test_qa_alerts.py`, 17 in `test_qa_alerts_commands.py`, plus `test_qa_deployment.py` and `test_local_rag_service.py`).
- `CI=true ./scripts/init.sh --fast`: all 10 checks passed; backend `2596 passed, 7 skipped, 1 warning`.
- Offline guard: tests use fake `launchctl`/Docker/Tailscale shell scripts (`MANIJERO_LAUNCHCTL_CLI` etc.), in-process fakes, and a fake Telegram `HTTPServer` on `127.0.0.1:0`; `MANIJERO_TELEGRAM_API` accepts only `http://127.0.0.1:<port>`, the command tests default it to the closed port `9`, and a test asserts every recorded launchctl call is `print|bootstrap|bootout` naming `org.manijero.qa-alerts`. No real launchctl, Docker, Tailscale, Telegram, or internet is called. `--verify` not run: no Android/Desktop/Gradle/packaging change.
- Implementation choices to check: one problem kind per check (priority down, not ready, erroring, unreachable), so an erroring QA that is also unreachable reports erroring only; stopped-on-purpose counts as an OK check (2 needed for recovery); a problem message suppressed by the 60-minute cap sends no recovery message; `qa_deployment.read_tailscale(cli, port)` is the only refactor (the old `_read_tailscale(ports)` delegates to it), plus `is_qa_container`. Setup's positive path is covered in process (it needs a Terminal); the subprocess tests cover its no-terminal refusal.
- Owner walkthrough: pending owner walkthrough (real Telegram, launchd, QA running).

## Validator checklist

- [ ] Focused block passes offline; no real launchctl, Docker, Tailscale, or Telegram call in tests.
- [ ] Five owner commands follow operations.md (prerequisites first, one `Result:` line, exit 0/1/2, idempotent start/stop, read-only status).
- [ ] Classification, debounce, 4-hour reminder, 60-minute cap, recovery, stopped-on-purpose, and lock skip behave as scenarios 4–5.
- [ ] Error threshold and window are read from `thresholds.json` (not duplicated) and match the dashboard's Problem level.
- [ ] Token and chat id only in `~/manijero/alerts/credentials/telegram.json` (0600); never in argv, plist, output, logs, state, or exception text; no `ts.net` address, names, client ids, question/answer/land text in messages.
- [ ] launchctl is only called for `org.manijero.qa-alerts`; plist carries no secret or `MANIJERO_*`.
- [ ] `qa_deployment.py` behavior unchanged; no new dependency; service never imports `qa_alerts`.
- [ ] Docs per the contract within budgets; operations.md amendment cites owner decision 2026-11-07; known limitation for a sleeping/off Mac recorded.
- [ ] Acceptance: owner walkthrough done, or accept recorded as `pending owner walkthrough`.

## Handoff

- Status: `passing`; validator 2026-11-07 returned accept with condition `pending owner walkthrough` (`docs/validations/qa_service_alerts.md`). Holding commit made on `feature/qa_service_alerts`.
- Next: owner runs `docs/owner-guide.md` "Owner walkthrough: QA alerts" (6 steps). If every step matches, orchestrator records it as evidence only, sets `accepted`, commits `feat: complete qa_service_alerts`; no second validator. A defect goes back to the implementer.
- Last checks: `--feature qa_service_alerts` 195 passed; `CI=true --fast` all 10 checks passed.
