# Validation: nightly_evaluation

- Verdict: accept (independent, final per owner decision; no owner walkthrough, `test_nightly_eval_commands.py` stands in).
- Spec: [nightly_evaluation.md](../specs/nightly_evaluation.md); evidence: [appendix](../specs/nightly_evaluation.appendix.md).

## Checks rerun

- `./scripts/init.sh --feature nightly_evaluation`: syntax checks ok; 312 passed, 1 skipped; real `--no-judge --answer-cache-check` run: 92 questions (17 reviewed, 49 golden, 26 trap), "79 of 92 reused unchanged (0 differed)"; `knowledge/` and the quality-gate baseline unchanged.
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 3576 passed, 9 skipped).
- `--verify` not rerun: the diff touches only `backend/`, `scripts/` shell, monitoring files, and docs (no `shared/`, apps, Gradle, packaging).

## Implementer deviations judged

- `MANIJERO_NIGHTLY_EVAL_REPORTS_ROOT` (test-only): lets the fake child write reports into a temp folder; it only redirects where the report is read, no production default changes. Accepted.
- One line in `backend/app/main.py`: passes `read_nightly_eval()` to the metrics renderer. Required to meet Scenario 7; accepted.
- Telegram and `launchctl` wired in `backend/scripts/nightly_eval.py` (using `qa_alerts` unchanged), keeping `app/nightly_eval.py` free of the alert module. Accepted; same ports, tested.
- `test_local_rag_service.py` and `test_container_image_files.py` made hermetic (stated `HOME`, temp state-folder variables) so a real `~/manijero` folder cannot change results. This removes machine dependence and masks nothing. Accepted.

## Isolation

The command tests use temp folders, a fake `launchctl` script, a fake metrics program, and a loopback fake Telegram with a fake token. No real `launchctl`, Telegram, `~/Library/LaunchAgents`, or `~/manijero` is used.

## Limits that remain

- A Mac that is off misses the run; the dashboard shows scores only while the local service and monitoring run.
- Faithfulness needs Ollama at run time; night-to-night comparison misses slow drift and flags expected drops (documented in `known-limitations.md`).
- The real launchd load and a real Telegram message were not exercised (by owner decision, covered by fakes only).
