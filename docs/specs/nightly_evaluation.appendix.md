# Appendix: `nightly_evaluation`

Contract: [`nightly_evaluation.md`](nightly_evaluation.md). This file holds research, planning-decision reasons, plan, verification plan, evidence, and the validator checklist.

## Repository research

Inspected (planner, 2026-11-11; no shell was available to the planner, so `select-feature.sh` was not run — the feature id came from the parent prompt):

- `feature_list.json` — `testing`, `not_started`, depends on `ci_quality_gates` and `answer_cache` (both accepted); no feature depends on it.
- `PROGRESS.md` "Current state" — `nightly_evaluation` is one of the 2 `not_started` features; `monitoring_dashboard`, `qa_service_alerts`, `knowledge_ops_orchestrator`, `evaluation_metrics_report`, `ci_quality_gates`, `answer_cache` accepted.
- `docs/archive/MasterPlanV3.md` lines 484, 506, 797 — "PR (subset) and nightly (complete)"; response caching by hash to save provider quota; C6 "Daily report".
- `docs/specs/evaluation_metrics_report.md`, `backend/scripts/evaluate_metrics.py` — `_run_cases` builds `create_app(..., answer_cache=None, answer_inspection=True)` with corpus/as-of/campaign/k overrides and `answer_eval.evaluate(...)`; `main(argv, *, reports_root, judge_options)`; faithfulness via `judge_grounding.main` with captured stdout; exit `2` on `MetricsAbort`; `Result:` line ends `Report: build/eval-reports/<id>/metrics.json.`
- `docs/specs/answer_cache.md` — owner decisions: memory only, cleared on restart, per process; a hit carries no `inspection`; clarifications and pre-check abstentions are not cached.
- `backend/app/ask_api.py` lines 297–592 — `get_answer_cache`; `_answer_through_cache` only when the corpus is a `Retriever`; `from_cache` suppresses inspection.
- `docs/specs/ci_quality_gates.md`, `docs/constraints/answers-and-knowledge.md` lines 148–175 — golden/trap/judge numbers never block; metrics report report-only, writes only under `build/eval-reports/`.
- `docs/specs/knowledge_ops_orchestrator.md`, `backend/app/knowledge_ops.py` — launchd plist (`StartCalendarInterval`), `_Lock`, ledger with `run_started`/`run_finished`, `metrics_snapshot`, `turn_on`/`turn_off`, child step runner with terminate-then-kill, `MISSED_AFTER`/`INTERRUPTED_AFTER`, `MADRID` zone.
- `docs/specs/qa_service_alerts.md`, `backend/app/qa_alerts.py` — `load_credentials`, `HttpTelegram`, `send_text`, `SystemLaunchctl` (optional `label`), test seams `MANIJERO_ALERTS_HOME`, `MANIJERO_TELEGRAM_API`, `MANIJERO_LAUNCHCTL_CLI`, `MANIJERO_LAUNCH_AGENTS_DIR`.
- `docs/specs/monitoring_dashboard.md`, `backend/monitoring/prometheus/rules.json` line 48–49 (`manijero:status_knowledge_updates` expression to mirror), `thresholds.json`, `grafana/dashboards/manijero-health.json` lines 946–984 (value-mapped sentences).
- `backend/app/health_metrics.py` lines 28–95 — `LABEL_NAMES` allowlist (no `metric` yet), `FAMILIES`, knowledge-ops reader pattern (`KNOWLEDGE_OPS_STATE_DIR_ENV`, lazy import of `metrics_snapshot`).
- `scripts/commands/knowledge.sh` lines 1–23 (dispatch block to copy), `scripts/lib/usage.sh` lines 96–105.
- `docs/constraints/operations.md` — owner-operability MUSTs; line 28 (automated walkthrough accepted for knowledge ops); Monitoring lines 37, 40–41 (Telegram rules, alert channel the owner already uses, not more than once per hour).
- `docs/owner-guide/` — topic files; `knowledge-updates.md`, `qa-alerts.md`, `monitoring.md`, `grounding-judge.md` (`--grounding-judge-setup` makes the judge available).

Not inspected: `judge_grounding.py` internals and real judge timing (never measured; no real judge run exists), `answer_eval.evaluate` row internals, `local_rag_service.py` env allowlist lines, `tests/test_monitoring_files.py` static checks in detail.

## Planning-decision reasons

1. Cache check: the owner's answer-cache decisions forbid disk or cross-process caching, so "with cached answers" cannot mean reusing last night's answers. Scoring with the cache on would remove `inspection` on hits and make ranks `null`, distorting hit@k/MRR, so the scored pass stays cache-off and a separate replay checks that what the cache serves equals what was scored.
2. 3-hour budget: a hung Ollama or judge must not block the next night; no measured judge time exists, so the bound is generous and recorded as a limit.
3. Telegram reuse: `operations.md` requires the channel the owner already uses; QA alerts set it up.
4. Strict 4-decimal comparison against the previous evaluated run, matching the owner's "drops compared with the previous run" and `ci_quality_gates`' zero tolerance; denominators can change, so `inputs_changed` explains expected drops.
5. Alerts only for drops (owner decision); failed/missed runs stay on dashboard and status. See open question below.

Open question for the owner (not blocking): should a failed, stopped, or missed nightly run also send a Telegram message? The spec says no, per the literal decision.

## Implementation plan

1. `eval_metrics.py`: `answer_cache_check` block builder, optional `version["answer_cache_check"] = True`, and the `Result:` suffix only when present; tests that default output is byte-identical.
2. `evaluate_metrics.py`: `--answer-cache-check`; collect scored responses (minus `inspection`) by case id in `_run_cases`; second app with `AnswerCache()` and the same overrides; fill pass + replay pass; hit delta from the app's `/metrics`; compare canonical JSON.
3. `nightly_eval.py`: home/paths, lock, ledger read/append (`nightly-eval-ledger-v1`), score extraction from `metrics.json` `overall` blocks, `compare`, `alert_text`, summary renderer.
4. Child runner port: spawn `evaluate_metrics.py run --as-of <Madrid date> --answer-cache-check` with timeout = time left; terminate, kill after 10 s; parse `Report:` path or abort code.
5. Alert sender: `load_credentials` → `send_text` up to 3 tries with injected sleep; record `sent|not_sent|not_set_up|not_needed`.
6. `status`, `turn_on`/`turn_off` (plist 00:00), `metrics_snapshot`.
7. `backend/scripts/nightly_eval.py` thin CLI with exit codes 0/1/2/3; `knowledge.sh` dispatch and `usage.sh` lines.
8. `health_metrics`: `MANIJERO_NIGHTLY_EVAL_STATE_DIR` reader, six families, `metric` label; `local_rag_service` env pass-through when the folder exists.
9. Monitoring: threshold, rule, "Nightly evaluation" row (status + score stats); static checks.
10. Docs per the contract list; evidence below.

## Verification plan

- `test_nightly_eval.py` (sockets blocked; fake clock/sleep/child/Telegram): happy path ledger, summary ≤10 lines, exit `0`; first run `first_run` and no send; drop on each score key sends exactly one message with expected text; equal and improved values send nothing; `null` faithfulness on either side not compared; `inputs_changed` sentence; failed base run skipped; child exit 2 → `failed` code; time limit kills child; send retried 3 times then `not_sent`; missing credentials → `not_set_up`; lock exit 3; marker question/answer text and fake token never appear in ledger, summary, log, plist, or stdout; `knowledge/` unchanged.
- `test_nightly_eval_commands.py` (automated owner walkthrough through `scripts/init.sh`, temp HOME, fake `launchctl`, fake child, loopback Telegram): `run` before setup → missing-prerequisite sentence, exit 2; `on` twice idempotent; plist content (Hour 0 Minute 0, no `MANIJERO_*`); `run` with a failing child → `failed`; recovery `run` → `evaluated`; a dropping run → alert received; `status` outputs and exit codes; `off` keeps history; extra argument exit 2.
- Extended: `test_eval_metrics.py`/`test_evaluate_metrics_command.py` (cache block, default byte-identity, forced mismatch counts `differed`), `test_health_metrics.py` (families, `metric` clamp, unreadable folder), `test_monitoring_files.py`, `test_local_rag_service.py`.
- Then `./scripts/init.sh --fast`.

## Evidence to capture

Focused block result lines (including the real `cached answers:` suffix), `--fast` result, one sample `latest-summary.txt` and one sample alert text from a fake run, the generated plist with paths redacted to `~`, and the changed-file list.

## Feature evidence

Implementer, 2026-11-11 (no owner walkthrough, owner decision; fakes only, no real launchctl, Telegram, LaunchAgents, or `~/manijero` folder touched).

- `./scripts/init.sh --feature nightly_evaluation`: passed; backend tests `312 passed, 1 skipped`; the real `--no-judge --answer-cache-check` run ended `... Report: build/eval-reports/<id>/metrics.json; cached answers: 79 of 92 reused unchanged (0 differed).`; `knowledge/` and the quality-gate baseline unchanged.
- `./scripts/init.sh --fast`: passed; `backend-tests 3576 passed, 9 skipped`, `harness-tests 23 passed`, all 10 offline checks ok.
- New tests: `test_nightly_eval.py` (33), `test_nightly_eval_commands.py` (10, automated owner walkthrough through `scripts/init.sh`); extended `test_eval_metrics.py`, `test_evaluate_metrics_command.py`, `test_health_metrics.py`, `test_monitoring_files.py`, `test_local_rag_service.py`.
- Sample fake-run summary: `Nightly evaluation on 2026-11-11 00:00 (took 2 min).` / `How it went: evaluated.` / two score lines / `Compared with the last run: no score dropped.` / `Report: <id>.`
- Sample alert: `Manijero nightly evaluation: 1 score(s) dropped since the last run: average source rank score (MRR) 0.7500 -> 0.6000. First step: open the health dashboard, then run ./scripts/init.sh --nightly-eval-status.`
- Plist (paths as `~`): Label `org.manijero.nightly-eval`, `ProgramArguments` `[~/.../backend/.venv/bin/python, ~/.../backend/scripts/nightly_eval.py, run, --scheduled]`, `StartCalendarInterval {Hour: 0, Minute: 0}`, `EnvironmentVariables {PATH}` only.
- Deviations to review: (1) added test-only seam `MANIJERO_NIGHTLY_EVAL_REPORTS_ROOT` (the child's reports must land in a temp folder in tests); (2) `nightly_eval.py` does not import `qa_alerts` (the operator-module test forbids it): the script wires `qa_alerts.load_credentials`, `HttpTelegram`, `send_text`, and `SystemLaunchctl(label=...)` unchanged behind small ports; (3) two existing tests (`test_local_rag_service`, `test_container_image_files`) read the real `~/manijero/knowledge-ops` through `Path.home()`; they now state `HOME`/the run-folder variables so they are hermetic.

## Validator checklist

- [ ] Owner decisions honored: 00:00 local schedule; dashboard row; one alert per run only on a drop vs the previous evaluated run; acceptance by automated tests; nothing pushed.
- [ ] Scored pass unchanged and cache-off; default `evaluate_metrics` output and `version_id` byte-identical; cache check compares replay vs scored responses without `inspection`.
- [ ] No score changes any exit code; no gate, baseline, `/ask`, `knowledge/`, or answer-cache change.
- [ ] Ledger, summary, alerts, metrics, and logs hold no question/answer/passage/land/token text; token only in-process.
- [ ] `launchctl` only for `org.manijero.nightly-eval`; 3-hour limit; lock; exit codes 0/1/2/3 as specified.
- [ ] Dashboard rule and panels match `thresholds.json`; `metric` label added to both allowlists.
- [ ] Durable docs updated per the contract; owner guide ≤60 lines; `backend/README.md` ≤30 lines.
- [ ] Focused block and `--fast` rerun independently and pass.
