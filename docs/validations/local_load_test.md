# `local_load_test` acceptance

## Verdict

**Accepted by the independent validator on 2026-11-06, with the condition `pending owner walkthrough`.**
Everything the automated tiers can reach is verified. The real measurement on the owner's Mac and the
walkthrough in the [owner guide](../owner-guide.md#owner-walkthrough-load-test) are owner-run by the
spec, so they are recorded as evidence when the owner reports them; the feature stays `passing` until
then.

## Independent verification

- Validator: focused block (`58 passed, 2 skipped`) and `--fast` (10/10 checks `[ok]`, backend
  `1913 passed, 4 skipped`) passed; `--verify` not rerun because no shared, Android, Desktop, or
  Gradle surface changed.
- Scope: diff is exactly the expected files; no change under `backend/app/`, `knowledge/`,
  `contracts/`, pins, requirements, or Kotlin/Gradle.
- Command wiring: `--check` lists `--local-rag-load-test`; an extra argument exits `2` with the
  "on its own" sentence; an empty temporary home exits `1` and creates only `.load-test.lock`.
- Request path, checked independently against a throwaway loopback server: one `/ask` per request
  with `{"question": …, "land_context": {"mode": "general", "lands": []}}`, only `status` kept, a
  `503` counted as a failed request with no invented latency, and no text retained.
- Scenarios 1–9: the gate and stale record, all five failing-check kinds, busy lock, Ctrl+C, failed
  warm-up, ramp/steady failures, both mid-run change flags, the `0600` aggregate-only report, sentinel
  privacy, and `app.main` never importing the measurement script.
- Durable documentation: `ARCHITECTURE.md` line, the `operations.md` MUST with `Reason:
  local_load_test`, the Medium risk row, the `backend/README.md` subsection, and the owner-guide
  section plus walkthrough.

## Pending

- Owner walkthrough steps 1–5 on the owner's Mac: the missing-prerequisite result, the
  Ollama-closed `PROBLEM` line, and one clean measured run (exit `0`, about five minutes) with the
  median, p95, slowest time, requests per second, finish/failure counts, and answer kinds.
- At that point the result is recorded as an evidence-only update, the status becomes `accepted`, and
  `PROGRESS.md` and `docs/progress/known-limitations.md` gain their acceptance line.

## Limits

- No real measurement was run by an agent; no real service or Ollama was contacted, and no report,
  lock, or log was written outside temporary test homes.
- Numbers from one Mac are host-specific evidence, not a capacity measurement; the pilot host is
  unmeasured, and the service hides whether each answer used the drafting model.
