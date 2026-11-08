# `local_load_test` acceptance

## Verdict

**Accepted by the independent validator on 2026-11-06; the condition `pending owner walkthrough` was met on 2026-11-07.**
Everything the automated tiers can reach is verified, and the owner ran the walkthrough in the
[owner guide](../owner-guide/local-checks.md#owner-walkthrough-load-test) on 2026-11-07 (evidence below).

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

## Owner walkthrough (2026-11-07)

Steps 1–5 passed on the owner's Mac with no difference from the guide: the missing-prerequisite and
Ollama-closed refusals, then one clean measured run (`Result: the load test finished`). Aggregates
only, reported by the owner from `local-load-measurement-v1` (release `3050d1b8b5e10f82`):

| Phase | Requests | Failed | Median | p95 | Max |
|---|---|---|---|---|---|
| Warm-up | 2 | 0 | 4.63 s | 6.89 s | 6.89 s |
| Ramp (10 s) | 14 | 0 | 10.11 s | 10.15 s | 10.15 s |
| Steady (180 s) | 1844 | 0 | 0.70 s | 1.18 s | 10.77 s |

Steady throughput 10.24 requests per second; 10 clients, 60 s timeout, no timeouts; the service was
neither changed nor stopped during the run. Answer-kind counts were not reported. The slow ramp and
the slowest request are consistent with the drafting model loading under the first simultaneous
requests (an interpretation, not measured). One Mac, host-specific: no pass/fail, capacity, or
pilot-readiness claim.

## Limits

- No real measurement was run by an agent; no real service or Ollama was contacted, and no report,
  lock, or log was written outside temporary test homes.
- Numbers from one Mac are host-specific evidence, not a capacity measurement; the pilot host is
  unmeasured, and the service hides whether each answer used the drafting model.
