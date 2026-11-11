# Feature Spec: `nightly_evaluation`

## Source metadata

- `id`: nightly_evaluation · `area`: testing · `depends_on` (both accepted): ci_quality_gates, answer_cache · `status` at planning: not_started.
- Source: `feature_list.json` title "Run the complete evaluation nightly with cached answers and a report"; `docs/archive/MasterPlanV3.md` C6 "Complete set; response caching → daily report" (historical only).
- User-visible behavior: once turned on, the owner's Mac runs the complete evaluation (17 reviewed cases, approved golden items, approved traps, and the grounding judge when it is available) every night at 00:00, with an answer-cache check. Each run's scores appear on the health dashboard, and one plain Telegram message is sent when a score is lower than in the previous run. Four named commands turn it on, run it now, show its status, and turn it off.
- Verification: offline pytest with a fake clock, fake child program, fake `launchctl`, fake Telegram on loopback, sockets blocked, and fake tokens only; one real `--no-judge --answer-cache-check` metrics run; an automated command walkthrough replaces the owner walkthrough.
- Notes — owner decisions (verbatim):
  - Run the golden and trap evaluation every night at 00:00 local time.
  - Results go to the monitoring dashboard, and an alert is sent when a score drops compared with the previous run.
  - No owner walkthrough unless strictly necessary; automated tests stand in for it. Plan acceptance around automated tests, not an owner walkthrough.
  - Do not push.
- Planning decisions (stricter than the owner decisions, never looser; reasons in the appendix):
  1. "Cached answers" means the accepted in-memory answer cache (`answer_cache`), which the owner limited to memory only and to one process. The nightly run therefore adds a **cache check** inside the run: a fresh in-process app with its own cache asks every case twice, and the second answer must come from the cache unchanged. The scored pass stays cache-off, exactly like `evaluate_metrics.py` today, so its numbers remain comparable. Nothing is cached across nights or written to disk.
  2. The schedule is a launchd user agent `org.manijero.nightly-eval` on the owner's Mac (like `knowledge_ops_orchestrator`). The run has a hard time limit of 3 hours. There are no retries, because the evaluation is deterministic.
  3. The alert channel is the Telegram bot the owner already set up for `qa_service_alerts`. No new channel, account, or paid service.
  4. "Score" means one of eight fixed overall values (table in Scenario 4). A drop means today's value, rounded to 4 decimals, is strictly lower than the previous evaluated run's value. A value that is missing on either side (for example faithfulness "not judged") is not compared.
  5. Owner commands and messages are in English, like every existing owner command.

## Goal

Every morning the owner can see on the dashboard how the assistant scored overnight on the reviewed, golden, and trap questions. If a score got worse, a Telegram message names which one, so a regression never goes unnoticed for long. The owner does not need to run anything.

## Non-goals

- A gate. No score changes an exit code, blocks a merge, a release, or a publish, or changes `/ask`, thresholds, retrieval, the corpus, or the `ci_quality_gates` baseline.
- Caching answers across runs, on disk, or across processes. Changing the answer cache itself. Turning the cache on in the scored pass.
- New evaluation sets, metrics, or judge models. A GitHub Actions schedule. QA or container runs. Downloading models (the judge only runs if `--grounding-judge-setup` already ran).
- Alerts for anything other than a score drop (a failed or missed run appears on the dashboard and in status only). A new alert channel or Telegram setup flow.
- Any claim that the scores measure legal correctness or real-user accuracy.

## Job story

When something changes the knowledge, the code, or the date, I want my Mac to re-run the full evaluation overnight and tell me on my phone if any score got worse, so I can ask for a fix before testers notice.

## Acceptance scenarios

### 1. Turn on, off, and check the schedule
Given the backend tools are set up · When the owner runs `./scripts/init.sh --nightly-eval-on` · Then it creates `~/manijero/nightly-eval/` (`0700`), installs `~/Library/LaunchAgents/org.manijero.nightly-eval.plist` (`StartCalendarInterval` Hour 0 Minute 0, absolute venv python and `backend/scripts/nightly_eval.py run --scheduled`, fixed PATH, no `MANIJERO_*` value or secret), loads it, and ends with `Result: the nightly evaluation is on. It runs every night at 00:00 while this Mac is on.` (exit `0`). Running it again prints "already on" and changes nothing. `--nightly-eval-off` removes only that agent and keeps the folder and history. `--nightly-eval-status` changes nothing. It prints on/off, the last run's outcome and local finish time, the scores with any drops, whether the alert was sent, and a `missed` warning (no run started in 30 h while on) or an `interrupted` warning (started, never finished within 4 h). It exits `0` only when the evaluation is on, the last run is `evaluated` within 30 h, and any needed alert was sent; otherwise it exits `1`. A score drop alone never changes this exit code. Any extra argument prints one sentence and exits `2`.

### 2. A run evaluates everything and records scores only
Given a fake child program that writes a valid metrics report · When `--nightly-eval-run` (or the schedule) starts · Then one child runs `backend/scripts/evaluate_metrics.py run --as-of <Europe/Madrid date at start> --answer-cache-check` with timeout = time left. The run reads the report the child names in its `Report:` path, appends `run_started` and `run_finished` (`outcome: evaluated`, `report_id`, the scores, `faithfulness` status, `inputs_changed`, drops, alert state) to `nightly-eval-ledger.jsonl` (`0600`), writes `latest-summary.txt` (at most 10 lines), prints the summary and one `Result:` line, and exits `0` whether or not a score dropped. The report stays under `build/eval-reports/`. The ledger, summary, output, and logs hold only ids, codes, counts, scores, and times, never question, answer, passage, land, token, or exception text. `knowledge/` is byte-identical afterwards.

### 3. The cache check proves cached answers equal scored answers
Given `evaluate_metrics.py run --answer-cache-check` · Then after the scored pass (cache off, unchanged), a second in-process app with a fresh `AnswerCache` asks every case once (filling the cache) and once more. Each replayed response, with `inspection` removed, is compared as canonical JSON with that case's scored response, also with `inspection` removed. The report gains `answer_cache_check` `{asked, served_from_cache, reused_unchanged, differed}`, where `reused_unchanged` counts replays that were cache hits and matched. `version` gains `"answer_cache_check": true`. The `Result:` line ends `; cached answers: <reused_unchanged> of <asked> reused unchanged (<differed> differed).` Without the flag, the report, `version_id`, and `Result:` line stay byte-identical to today. Served-from-cache is read from the app's `manijero_answer_cache_lookups_total{outcome="hit"}` delta.

### 4. Drops compared with the previous evaluated run
The scores are hit@1, hit@3, hit@5, MRR, abstention share, numbers-and-dates share, faithfulness `supported_share` (only when `judged`), and cache reuse (`reused_unchanged ÷ asked`). Given a previous `evaluated` run in the ledger · When a score is strictly lower (4 decimals) · Then the drop is recorded with old and new values. Given no previous evaluated run · Then nothing is compared, the run is marked `first_run`, and no alert is sent. Failed, stopped, or interrupted runs are never the comparison base. `inputs_changed` is true when any `version` digest or setting other than `as_of` differs from the base run.

| Score key | Plain label in messages and on the dashboard |
|---|---|
| `hit_at_1` / `hit_at_3` / `hit_at_5` | right source first / in the top 3 / in the top 5 |
| `mrr` | average source rank score (MRR) |
| `abstention` | correct refusals |
| `numeric` | numbers and dates correct |
| `faithfulness` | sentences the judge found supported |
| `cache_reuse` | cached answers reused unchanged |

### 5. One Telegram alert per run with drops
Given at least one drop and valid Telegram details in `~/manijero/alerts/credentials/telegram.json` · Then exactly one message is sent: `Manijero nightly evaluation: <N> score(s) dropped since the last run: <label> <old> -> <new>; …` followed by ` The questions or the knowledge changed since the last run, so a drop may be expected.` only when `inputs_changed`, and ending ` First step: open the health dashboard, then run ./scripts/init.sh --nightly-eval-status.` Shares are shown as percentages with one decimal, and MRR with 4 decimals. A send is tried at most 3 times, 10 s apart (injected sleep). When it still fails, or the details are missing, it records `alert: not_sent` or `not_set_up`, and status names `--qa-alerts-test` or `--qa-alerts-setup` as the fix. A later run never re-sends an old drop. The message holds only fixed text, labels, and numbers. The token and chat id are used only in-process (never argv, output, logs, ledger, or plist).

### 6. Failures, time limit, and one run at a time
Given the child exits `2` · Then the outcome is `failed` with the code from its `Result:` line (`invalid_inputs`, `ask_failed`, `unsafe_report_path`, `internal_error`, or `child_output_unreadable`), no scores are recorded or compared, and the run exits `1`. Given the child is still running 3 hours after start · Then it is terminated, then killed after 10 s, the outcome is `stopped_at_time_limit`, and the run exits `1`. Given the backend tools or `launchctl` are missing · Then nothing changes, one plain sentence names the fix command, and the run exits `2`. Given another run holds `nightly-eval.lock` · Then nothing starts, no ledger line is written, and the run exits `3`. Tracebacks go only to `~/manijero/nightly-eval/logs/nightly-eval.log` (`0600`).

### 7. Dashboard row
Given the local service runs with `--local-rag-start` and the folder exists · Then `GET /metrics` carries `manijero_nightly_eval_configured`, `_readable`, `_last_run_outcome{outcome}` (`evaluated|failed|stopped_at_time_limit|interrupted`), `_last_run_finished_timestamp_seconds`, `_score{metric}` (fixed keys above, present only when not null), and `_score_dropped{metric}` (0/1). The dashboard gains a "Nightly evaluation" row: one status check (rule `manijero:status_nightly_eval`), plus one stat per score with its plain label (missing shows `Not measured`). The status check reads OK when the last run was `evaluated` within 30 h with no drop. It reads Warning when no run finished in 30 h. It reads Problem, with two sentences, when the run failed, stopped, or was interrupted, or when a score dropped. It reads `Not set up yet` or `No information yet` otherwise. Each state names `--nightly-eval-status` as the first thing to do.

## Technical approach

- `backend/app/nightly_eval.py` (stdlib plus `app`): constants (`LABEL`, `SCHEDULE_HOUR = 0`, `SCHEDULE_MINUTE = 0`, `BUDGET = 3 h`, `MISSED_AFTER = 30 h`, `INTERRUPTED_AFTER = 4 h`, `SEND_TRIES = 3`, `SCORE_KEYS`), a `Ports` dataclass (clock, sleep, child runner, launchctl, Telegram transport, output, paths), `run_once`, `compare(previous, current)`, `alert_text`, `status`, `turn_on`/`turn_off`, `metrics_snapshot(folder, now)`, and the `nightly-eval-ledger-v1` JSON Lines ledger. It reuses `knowledge_ops`'s lock, ledger, child-kill, and plist patterns and `qa_alerts.SystemLaunchctl(label=...)`, `load_credentials`, `HttpTelegram`, and `send_text` unchanged.
- `backend/scripts/evaluate_metrics.py` + `backend/app/eval_metrics.py`: an optional `--answer-cache-check` flag (Scenario 3). The scored pass, isolation, and default output stay as they are.
- `backend/scripts/nightly_eval.py on|off|run|status`. `scripts/commands/knowledge.sh` dispatches `--nightly-eval-on|-off|-run|-status` like `--knowledge-updates-*`, and `scripts/lib/usage.sh` lists them.
- `health_metrics` reads `MANIJERO_NIGHTLY_EVAL_STATE_DIR` like the knowledge-ops reader and adds `metric` to `LABEL_NAMES` (and to the Prometheus `labelkeep` list in `local_monitoring.py` if that list is not derived from it). `local_rag_service` passes that variable only when the folder exists. The monitoring threshold (`nightly_evaluation.stale_hours: 30`), the rule (codes `-1/0/1/2/3/4`, where `3` = score dropped), and the panels follow `monitoring_dashboard`.
- Test-only seams: `MANIJERO_NIGHTLY_EVAL_HOME`, `MANIJERO_NIGHTLY_EVAL_CHILD_CLI`, `MANIJERO_NIGHTLY_EVAL_NO_WAIT`, plus the existing `MANIJERO_LAUNCHCTL_CLI`, `MANIJERO_LAUNCH_AGENTS_DIR`, `MANIJERO_ALERTS_HOME`, and `MANIJERO_TELEGRAM_API` (loopback only).

## Expected file changes

- Create: `backend/app/nightly_eval.py`, `backend/scripts/nightly_eval.py`, `backend/tests/test_nightly_eval.py`, `backend/tests/test_nightly_eval_commands.py`, `docs/owner-guide/nightly-evaluation.md`.
- Modify: `backend/app/eval_metrics.py`, `backend/scripts/evaluate_metrics.py`, `backend/app/health_metrics.py`, `backend/app/local_rag_service.py`, `backend/monitoring/{thresholds.json,prometheus/rules.json,grafana/dashboards/manijero-health.json}`, `scripts/commands/knowledge.sh`, `scripts/lib/usage.sh`. Extend these tests: `test_eval_metrics.py`, `test_evaluate_metrics_command.py`, `test_health_metrics.py`, `test_monitoring_files.py`, `test_local_rag_service.py`.
- Do not change: `answer_cache.py`, `ask_api.py`, `quality_gate.py`, the quality-gate baseline, `knowledge/`, `contracts/`, `.github/`, `qa_alerts.py`/`knowledge_ops.py` behavior, the apps, or requirements.
- Implementer/validator only after evidence: `feature_list.json` status, `PROGRESS.md`, `docs/progress/*`, `docs/validations/nightly_evaluation.md`.

## Visual design impact

App UI: none. The dashboard row follows `monitoring_dashboard`: the state word is always in the text, there is no colour-only meaning, and it is readable at 200 % zoom.

## Durable documentation impact

- `docs/owner-guide/nightly-evaluation.md`: create (≤60 lines: on, run now, status, off, reading the alert, and a table of reachable `Result:` lines). List it in `docs/owner-guide/README.md`, and add the row to `docs/owner-guide/monitoring.md`.
- `docs/constraints/operations.md`: update. Add one MUST: the nightly commands call `launchctl` only for `org.manijero.nightly-eval`, stop a run after 3 hours, keep one run at a time, send at most one fixed-text Telegram message per run and only for a drop, and are accepted through `test_nightly_eval_commands.py`, not an owner walkthrough (owner decision).
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation": update. Add one MUST: the nightly evaluation is report-only (no score changes an exit code or gate), compares only with the previous `evaluated` run, stores scores and codes only, and its cache check never caches across processes or to disk.
- `ARCHITECTURE.md`: update with one bullet. `backend/README.md`: update, ≤30 lines.
- `docs/progress/known-limitations.md`, `docs/risks-and-open-questions.md`: update. A Mac that is off misses the run (launchd runs it on wake only after sleep). The dashboard shows it only while the local service and monitoring run. Faithfulness needs Ollama at run time. Night-to-night comparison misses a slow drift and flags expected drops (date or knowledge changes).
- `AGENTS.md`, `CONSTRAINTS.md` index, `CONTEXT.md`, `DESIGN.md`, `contracts/`: not needed.

## Focused verification

`./scripts/init.sh --feature nightly_evaluation` runs this block unchanged from the repository root. It needs the backend environment but no Ollama, network, Docker, or service.

<!-- verify:start -->
```sh
bash -n scripts/init.sh && bash -n scripts/commands/knowledge.sh && bash -n scripts/lib/usage.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_nightly_eval.py tests/test_nightly_eval_commands.py tests/test_eval_metrics.py tests/test_evaluate_metrics_command.py tests/test_health_metrics.py tests/test_monitoring_files.py tests/test_local_rag_service.py tests/test_qa_alerts.py tests/test_knowledge_ops.py -q
out="$("${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_metrics.py run --as-of 2026-11-10 --no-judge --answer-cache-check)"; printf '%s\n' "$out" | tail -n 1; printf '%s\n' "$out" | grep -q '(17 reviewed, 49 golden, 26 trap)'; printf '%s\n' "$out" | grep -q 'reused unchanged (0 differed)'
git diff --quiet -- knowledge/ backend/config/quality_gate_baseline.json
```
<!-- verify:end -->

Manual acceptance: none. The validator's independent rerun of this block and of `./scripts/init.sh --fast` is final (owner decision).

## Appendix

See [`nightly_evaluation.appendix.md`](nightly_evaluation.appendix.md) for repository research, planning-decision reasons, the ordered plan, tests by behavior, evidence to capture, and the validator checklist.
