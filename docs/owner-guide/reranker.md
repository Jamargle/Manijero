# Reranker (optional second reading)

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains. Run the local answer setup first
([local answer service](local-answer-service.md): `./scripts/init.sh --local-rag-setup`).

## What it is

When someone asks a question, today's search finds a few official passages and puts them in an order.
A **reranker** is a second, more careful reader: it reads the question together with each found passage
and puts the passages in a new order, so the best one comes first. It never adds a passage, never
removes one, and never changes what the official text says. If it fails, the answer is built exactly as
before. **It is off. Nothing changes until you switch it on.**

## How it is measured

The measure command asks your reviewed questions twice, on this Mac: once with today's search, once
with the reranker added. It uses the 49 reviewed golden questions (is the right official source found?)
and the 26 trap questions (does the assistant still refuse or stay safe?). It prints only counts.

## Download the model (one time)

1. Paste `./scripts/init.sh --reranker-download`. It is about 2.3 GB and may take a while. If it stops,
   paste the same command again; it continues where it stopped.
   - Expected: `Result: the reranker model is downloaded and matches the reviewed copy (2.3 GB). It stays off until it is switched on.`
   - A second run says `Result: the reranker model is already downloaded and matches the reviewed copy; nothing was downloaded.`

## Measure it

1. Paste `./scripts/init.sh --reranker-measure` and wait; it prints `Checked question <n> of <N>` twice.
   - Expected: one line like `Result: reranker measured on 49 golden and 26 trap questions against today's hybrid search. Right source found: 40 today, 43 with the reranker (+3). Golden questions broken: 0. Trap questions worse: 0. Slowest extra time: 1.2 seconds. Verdict: ON - it met all the rules. Send this line to the developer.`
2. Send that line to the developer; do not switch anything yet.

## How to read the line

- **Right source found**: golden questions where the answer cites the right official source. More is better.
- **Golden questions broken**: questions that worked with today's search and stopped working. Must be 0.
- **Trap questions worse**: trick questions the assistant handled worse with the reranker. Must be 0.
- **Slowest extra time**: the most seconds it added to one answer. Must be 2 seconds or less.
- **Verdict ON** only if it finds at least 2 more right sources, and the three limits above hold.
  Otherwise **Verdict OFF**, with the reasons: it stays off and the result is kept as a recorded experiment.

## Switch it on or off

1. `./scripts/init.sh --reranker-on` switches it on; it refuses unless the downloaded model checks out.
   - Expected: `Result: the reranker is switched on. It is used from the next ./scripts/init.sh --local-rag-start.`
2. `./scripts/init.sh --reranker-off` switches it off. If the service is running, stop and start it to use the change.
3. `./scripts/init.sh --local-rag-service-status` shows one `Reranker:` line: `off`, `on`, or
   `switched on but the model is missing; answering without it`.

### If the command shows something else

| You see | What to do |
|---|---|
| `... did not run. Run ./scripts/init.sh --local-rag-setup.` or `... today's hybrid search is not ready ...` or `... did not run for every question ...` | Run `./scripts/init.sh --local-rag-setup`, then repeat. |
| `... not enough free disk space ...` | Empty the Trash, then repeat the download. |
| `... download did not finish ...` | Check the internet, then repeat; it continues where it stopped. |
| `... not the reviewed one ...`, `... not pinned yet`, or `... record is not valid` | Send the line to the developer; nothing was changed. |
| `... not switched on because its model is missing ...` | Run `--reranker-download`, then switch on. |

Your run of the download and measure steps above is the owner walkthrough: send the developer each `Result:` line.
