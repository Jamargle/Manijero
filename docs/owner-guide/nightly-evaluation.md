# Nightly evaluation

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

Every night at 00:00, while this Mac is on, Manijero runs the complete evaluation: the 17 reviewed
questions, the approved golden questions, the approved trap questions, and the grounding judge when
it is set up. It also checks that a repeated question is answered from the memory cache exactly as
before. The run stops after 3 hours. **It only reports: no score blocks anything.** A Mac that is
off at 00:00 misses that night's run.

1. **Turn on (one time).** Paste `./scripts/init.sh --nightly-eval-on`. Expect
   `Result: the nightly evaluation is on. It runs every night at 00:00 while this Mac is on.`
   Running it again says `already on` and changes nothing.
2. **Run now (optional).** Paste `./scripts/init.sh --nightly-eval-run`. It prints a short summary
   (10 lines at most) and ends with a `Result:` line. Telegram is told only when a score dropped.
3. **Check.** Paste `./scripts/init.sh --nightly-eval-status`. Expect the last run, its scores, and
   `Result: the nightly evaluation is on and the last run was evaluated.`
4. **Turn off.** Paste `./scripts/init.sh --nightly-eval-off`. Expect
   `Result: the nightly evaluation is off. Your history is kept.`

The latest summary is also in `manijero/nightly-eval/latest-summary.txt`. The health dashboard shows
a **Nightly evaluation** row (only while the local answer service runs).

**Reading the alert.** One Telegram message per run, only when a score is lower than in the previous
run, for example `Manijero nightly evaluation: 1 score(s) dropped since the last run: right source
first 73.2% -> 60.0%.` If it adds `The questions or the knowledge changed`, the drop may be expected.
Then run `./scripts/init.sh --nightly-eval-status`. The message uses the Telegram bot from
[QA alerts](qa-alerts.md); if it was not sent, the status says which command to run.

| You see | What it means | What to do |
|---|---|---|
| `The nightly evaluation is not set up yet.` | Step 1 was not done. | Run `./scripts/init.sh --nightly-eval-on`, then try again. |
| `The backend tools are not set up yet.` | The local tools are missing. | Run `./scripts/init.sh --local-rag-setup`, then try again. |
| `A nightly evaluation is already in progress.` | Another run is working. | Wait, then run `./scripts/init.sh --nightly-eval-status`. |
| `Code: invalid_inputs` / `ask_failed` / `unsafe_report_path` / `internal_error` / `child_output_unreadable` | The run failed; no scores were saved. | Run `./scripts/init.sh --nightly-eval-run` again; if it repeats, tell a developer (details in `manijero/nightly-eval/logs/nightly-eval.log`). |
| `stopped at the 3-hour limit` | The run took too long. | Run `./scripts/init.sh --nightly-eval-run` again; if it repeats, tell a developer. |
| `Alert: the message was not sent.` | Telegram did not answer. | Run `./scripts/init.sh --qa-alerts-test` and do what it says. |
| `Alert: ... not set up` in the status | Telegram details are missing. | Run `./scripts/init.sh --qa-alerts-setup`. |
| `Warning (missed)` in the status | No run started in 30 hours. | Run `./scripts/init.sh --nightly-eval-run`; keep the Mac on at 00:00. |
| `Warning (interrupted)` in the status | A run started and never finished. | Run `./scripts/init.sh --nightly-eval-run` again. |
| `Result: ... finished and 2 score(s) dropped.` | A score is lower than last time. | Read the summary above; ask a developer if the drop is not expected. |
