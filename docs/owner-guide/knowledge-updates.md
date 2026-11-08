# Knowledge updates

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

Once a day, at 10:20 while this Mac is awake, Manijero looks for new official documents, sorts them,
downloads and reads them, compares them with the approved sources, checks which sources are still
valid, and prepares a review folder. The whole run stops after one hour. **It never publishes
anything: you approve every change before it goes live.** A sleeping or switched-off Mac misses the
run; the next one starts at the next 10:20.

1. **Turn on (one time).** Paste `./scripts/init.sh --knowledge-updates-on`. Expect
   `Result: knowledge updates are on. A run starts every day at 10:20 while this Mac is awake.`
   Running it again says `already on` and changes nothing.
2. **Run now (optional).** Paste `./scripts/init.sh --knowledge-updates-run`. It prints a short summary
   (15 lines at most) and ends with `Result: the knowledge update run is ready for your review. ...`
3. **Check.** Paste `./scripts/init.sh --knowledge-updates-status`. Expect the last run and its summary
   file, then `Result: knowledge updates are on and the last run is ready for your review.`
4. **Turn off.** Paste `./scripts/init.sh --knowledge-updates-off`. Expect
   `Result: knowledge updates are off. Your history is kept.`

The latest summary is also in `manijero/knowledge-ops/latest-summary.txt`, and the health dashboard
shows a **Knowledge updates** box (only while the local answer service runs). The review folder is
`manijero/knowledge-ops/runs/<run>/review/REVIEW.md`; it lists what changed, never decides it.

Each step is tried up to 3 times (waiting 1, then 5 minutes). A step that still fails is named with
the first thing to do; the steps that need it say `not run`. Nothing is skipped silently.

| You see | What it means | What to do |
|---|---|---|
| `Knowledge updates are not set up yet.` | Step 1 was not done. | Run `./scripts/init.sh --knowledge-updates-on`, then try again. |
| `The backend tools are not set up yet.` | The local tools are missing. | Run `./scripts/init.sh --local-rag-setup`, then try again. |
| `A knowledge update run is already in progress.` | Another run is working. | Wait for it, then run `./scripts/init.sh --knowledge-updates-status`. |
| `The local drafting program (Ollama) is not running.` | Sorting needs Ollama. | Open Ollama, then run `./scripts/init.sh --knowledge-updates-run` again. |
| `An official source did not answer.` / `An official page could not be checked.` | No internet, or the site was down. | Check the internet, then run `./scripts/init.sh --knowledge-updates-run` again; if a page keeps failing, tell a developer. |
| `A setting or a saved file is not valid.` / `The approved sources or the downloaded documents could not be read.` | A file is damaged. | Tell a developer; the details are in `manijero/knowledge-ops/logs/knowledge-ops.log`. |
| `stopped at the one-hour limit` | The run took too long. | Run `./scripts/init.sh --knowledge-updates-run` again; if it repeats, tell a developer. |
| `Warning (missed)` in the status | No run started in 30 hours. | Run `./scripts/init.sh --knowledge-updates-run`; keep the Mac awake at 10:20. |
| `Warning (interrupted)` in the status | A run started and never finished. | Run `./scripts/init.sh --knowledge-updates-run` again. |
| `Result: knowledge updates were not turned on. ...` | macOS refused the schedule. | Run `./scripts/init.sh --knowledge-updates-on` again; if it repeats, tell a developer. |
