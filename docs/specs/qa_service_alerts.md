# Alert the owner on Telegram when the QA service is down, not ready, or erroring

## Source metadata

- `id`: qa_service_alerts · `area`: operations · `depends_on`: qa_server_deployment, monitoring_dashboard (both accepted) · `status` at planning: not_started
- User-visible behavior: after a one-time Telegram bot setup, the owner turns on a check that runs on their Mac every 5 minutes and sends one plain-language Telegram message when QA goes down, is not ready, is erroring, or stops answering at its public address, one "back to normal" message when it clears, and at most a reminder every 4 hours while it stays broken. Named commands set up, start, stop, check, and test the alerts, each ending with one `Result:` line.
- Verification: offline unit and `scripts/init.sh` subprocess tests with a fake Telegram, fake probes, fake Docker/Tailscale, and a fake `launchctl` (Focused verification); manual acceptance is the owner walkthrough in `docs/owner-guide/qa-alerts.md` ("Owner walkthrough: QA alerts").
- Notes — Owner decisions 2026-11-07:
  1. Alert channel: a Telegram bot the owner creates once, guided by a step-by-step owner-guide section; account and bot creation are never automated. The bot token and chat id live only in a local untracked secrets file outside the repository; they are never committed, printed, logged, or passed in argv.
  2. The check runs on the owner's Mac as a launchd user agent every 5 minutes, with one named start, one stop, and one status command, each ending with one plain `Result:` line.
  3. Alerts in plain language when the QA service is down (container not running or `/health` fails), not ready (`/ready` fails), or erroring (error rate from `/metrics` over the `monitoring_dashboard` thresholds), and when the public Tailscale https address stops answering `/health`.
  4. One alert when a problem starts, one "back to normal" message when it clears; no repeat spam, at most a reminder every few hours while still broken.
  5. A send-test-alert command lets the owner check the setup.
  6. No question or answer text, land context, names, client ids, or tokens in alerts.
  7. A sleeping or switched-off Mac cannot be detected; this is recorded in `docs/progress/known-limitations.md`.
  8. Zero cost; no new paid services.
  9. Tests are offline with a fake Telegram, fake probes, and fake launchctl (no network, no real launchctl calls).
  10. Acceptance: validator accept plus a short owner walkthrough (set up the bot, start the job, receive the test alert); the validator may accept with condition `pending owner walkthrough`.
- Planner decisions (reasons in the appendix): a fifth command `--qa-alerts-setup` stores the pasted bot token and finds the chat id (operations.md: the owner never edits files); "erroring" means the dashboard's **Problem** level (`errors.problem_percent`, window `errors.window` in `backend/monitoring/thresholds.json`), Warning stays dashboard-only; reminder interval 4 hours; a problem must be seen on 2 checks in a row before alerting; messages are English like every owner command; messages never include the `ts.net` address (it can carry the Mac or owner name).

## Goal

Tell the owner on their phone, in plain words and without spam, when QA stops working for testers and what to check first, at no cost.

## Non-goals

- Detecting a sleeping, switched-off, or offline Mac, or any check from outside the Mac; describing this as outage alerting for the host (operations.md Monitoring).
- Alerting on local services, answer speed, abstention rate, or the dashboard's Warning level; alerts for prod.
- Restarting or repairing QA automatically; changing `--qa-*` or `--monitoring-*` behavior, `/health`, `/ready`, `/metrics`, `thresholds.json`, `contracts/`, or the apps.
- Creating the Telegram account or bot, other channels (email, SMS, push), or any paid service.

## Job story

When QA breaks while testers use it, I want a short message on Telegram that says what is wrong and the first thing to do, and a second one when it is fine again, so I can look after QA without watching a dashboard.

## Acceptance Scenarios

### 1. Setup stores the Telegram details safely
Given the owner made a bot with BotFather (owner-guide steps) · When they run `./scripts/init.sh --qa-alerts-setup`, paste the bot token at a hidden prompt, send any message to the bot, and press Enter · Then the token is checked with Telegram, the chat id of the newest private chat is taken, both are written to `~/manijero/alerts/credentials/telegram.json` (directory `0700`, file `0600`), nothing about the bot, chat, or sender is printed, and it ends `Result: Telegram alerts are set up. Send a test with ./scripts/init.sh --qa-alerts-test.` (exit `0`). A malformed or rejected token, no private message found after 3 tries, no terminal, or Telegram unreachable stops with one sentence and its fix, writes nothing, exit `1`. When a file already exists it asks before replacing it (any answer but `yes` keeps it, exit `0`).

### 2. Test alert
When `./scripts/init.sh --qa-alerts-test` runs · Then it sends `Manijero QA: this is a test alert. If you can read it, alerts reach you.` and ends `Result: a test alert was sent. Check Telegram on your phone.` (exit `0`). Missing or unreadable secrets (or mode not `0600`), a rejected token, a blocked or unknown chat, or Telegram unreachable each print one sentence with its fix and `Result: the test alert was not sent. <fix>` (exit `1`).

### 3. Start, stop, status
`--qa-alerts-start` checks prerequisites first (secrets valid, QA settings hold a real `MANIJERO_PUBLIC_URL`, QA access keys complete, the backend venv exists), then writes `~/Library/LaunchAgents/org.manijero.qa-alerts.plist` (StartInterval 300, RunAtLoad, absolute venv python and `backend/scripts/qa_alerts.py check`, fixed PATH, no secret or `MANIJERO_*` value), loads it with `launchctl bootstrap gui/<uid>`, and ends `Result: QA alerts are on. The check runs every 5 minutes while this Mac is awake.`; already on with the same file: says so and changes nothing. `--qa-alerts-stop` unloads (`bootout`) and removes only that plist, keeps secrets and state, and ends `Result: QA alerts are off.` or `Result: QA alerts were not on, so there was nothing to stop.` (both exit `0`). `--qa-alerts-status` changes nothing and prints `OK`/`PROBLEM` lines for Alert job, Telegram (set up or not, never values), Last check (local time and outcome, or none yet, or older than 15 minutes with "the Mac may have been asleep"), and Open problems (kind, since when, alert sent or not); it ends `Result: QA alerts are on and the last check found no problem.` (exit `0`) or `Result: QA alerts need attention: <first fix>` / `Result: QA alerts are off. Turn them on with ./scripts/init.sh --qa-alerts-start.` (exit `1`). Any extra argument prints one sentence, exit `2`.

### 4. The check classifies QA
Each run of `qa_alerts.py check` finds, in this order: **down** (Docker Desktop closed, `manijero-qa` with the QA labels exists but is not running, or loopback `/health` fails), **not ready** (`/health` ok, `/ready` not ready), **erroring** (`/ask` 5xx share over the last `errors.window` from cumulative `/metrics` counters ≥ `errors.problem_percent`, with at least one `/ask`), and separately **unreachable** (local `/health` ok but `<MANIJERO_PUBLIC_URL>/health` does not answer). `/metrics` is read on loopback with the QA token in an in-process header. Until a full window of counter samples exists, or after a counter drop (restart), erroring is not judged. QA **stopped on purpose** (Docker ready, no `manijero-qa` container, Funnel not pointing at QA — the state `--qa-stop` leaves) is not a problem. While a QA command holds its lock, the check is skipped and nothing changes.

### 5. One alert per problem, one recovery, rare reminders
Given a problem is seen on 2 checks in a row · Then one message is sent naming the problem and its first step (table below). Given it stays · Then a reminder `Manijero QA: still a problem since <HH:MM>: …` is sent every 4 hours, never sooner. Given 2 OK checks in a row (or QA stopped on purpose) after an alert was sent · Then one `Manijero QA is back to normal (problem from <HH:MM> to <HH:MM>).` is sent. A change from one service problem to another sends one message for the new one; the same kind never gets a problem message twice within 60 minutes. A failed send is retried on the next check and never logs the request.

| Kind | Message after `Manijero QA: ` | First step in the message |
|---|---|---|
| down, Docker closed | `QA is down: Docker Desktop is not open.` | Open Docker Desktop, then run `./scripts/init.sh --qa-deploy`. |
| down | `QA is down: the QA service is not running or does not answer.` | Run `./scripts/init.sh --qa-status` on your Mac. |
| not ready | `QA is running but not ready to answer questions.` | Run `./scripts/init.sh --qa-status` on your Mac. |
| erroring | `QA failed on <N>% of questions in the last 15 minutes.` | Open the health dashboard, then run `./scripts/init.sh --qa-status`. |
| unreachable | `QA works on your Mac but phones cannot reach it.` | Open the Tailscale app, check you are logged in, then run `./scripts/init.sh --qa-status`. |

### 6. Privacy and safety
Then no message, output, log, plist, or state file contains a token, chat id, the `ts.net` address, question or answer text, land data, names, or client ids; the token is used only in-process (never argv, environment of children, or exception text); state and logs live under `~/manijero/alerts/` (`0600` files) and hold only times, kind codes, and counter numbers; `launchctl` is only ever called for the label `org.manijero.qa-alerts`.

## Technical approach

- New stdlib-only `backend/app/qa_alerts.py` (operator module, never imported by the service): injected ports for Docker (`lc.DockerCli`), Tailscale, loopback probes, public probe (`qa_deployment.system_public_probe`), metrics reader, Telegram transport, launchctl, clock, TTY/prompt; reuses `qa_deployment` container/label/Funnel/lock helpers (expose public names, no behavior change), `environment_profiles` (QA settings, credential paths), and `thresholds.json`.
- New entry `backend/scripts/qa_alerts.py <setup|start|stop|status|test|check>`; `scripts/init.sh` adds one `--qa-alerts-setup|start|stop|status|test` dispatch block like `--qa-*` and lists them in `usage`. `check` is launchd-only, not an owner command.
- Telegram Bot API over HTTPS (`getMe`, `getUpdates`, `sendMessage`, plain text). Test-only seams: `MANIJERO_ALERTS_HOME`, `MANIJERO_LAUNCHCTL_CLI`, `MANIJERO_LAUNCH_AGENTS_DIR`, `MANIJERO_TELEGRAM_API` (accepted only as `http://127.0.0.1:<port>`).

## Expected file changes

- Create: `backend/app/qa_alerts.py`, `backend/scripts/qa_alerts.py`, `backend/tests/test_qa_alerts.py`, `backend/tests/test_qa_alerts_commands.py`.
- Modify: `scripts/init.sh` (dispatch, usage); `backend/app/qa_deployment.py` (public aliases only); `backend/tests/test_local_rag_service.py` (add `qa_alerts` to the operator-module list).
- Not changed: `backend/monitoring/*`, service modules, `contracts/*`, `knowledge/*`, apps, Gradle files, `.gitignore`.

## Visual design impact

App UI involved: no. Owner text (terminal and Telegram) is plain English, state word in text, no colour-only meaning.

## Durable documentation impact (required)

- `docs/constraints/operations.md`: update — amend the "check that runs outside that host" MUST with owner decision 2026-11-07 (QA alerts run on the same Mac, detect service problems only while it is awake, never described as host-outage alerting); add one MUST for QA alerts (secrets only in `~/manijero/alerts/credentials/`, never argv/printed/logged; fixed message texts; launchctl only for its own label; 4-hour reminder, 60-minute same-kind cap).
- `ARCHITECTURE.md`: update — one bullet for `qa_alerts.py` (launchd check, Telegram).
- `docs/owner-guide/qa-alerts.md`: update (≤ ~60 lines) — "Set up Telegram alerts (one time)" (BotFather steps, `--qa-alerts-setup`), "Turn QA alerts on, check, test, and off" (table of `Result:` lines and the message table), "Owner walkthrough: QA alerts"; note the macOS "Background item added" notice.
- `backend/README.md`: update (≤ ~30 lines) — internals, plist keys, test seams.
- `docs/progress/known-limitations.md`: update — sleeping/off Mac undetectable; the public probe runs from the same Mac; erroring needs 15 minutes of samples.
- `PROGRESS.md`, session log: at acceptance. `AGENTS.md`, `CONSTRAINTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed.

## Focused verification (required)

Offline in `backend/.venv`: temporary `MANIJERO_ALERTS_HOME`, `MANIJERO_QA_HOME`, `MANIJERO_LAUNCH_AGENTS_DIR`; fake `MANIJERO_LAUNCHCTL_CLI`, `MANIJERO_DOCKER_CLI`, `MANIJERO_TAILSCALE_CLI`; fake Telegram on a loopback test socket; fake tokens only.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_qa_alerts.py tests/test_qa_alerts_commands.py tests/test_qa_deployment.py tests/test_local_rag_service.py -q
```
<!-- verify:end -->

The owner walkthrough (real Telegram, launchd, QA running) is manual acceptance recorded by the orchestrator, not part of this block.

## Appendix

See [`qa_service_alerts.appendix.md`](qa_service_alerts.appendix.md) for research, planner decisions, plan, evidence, and the validator checklist.
