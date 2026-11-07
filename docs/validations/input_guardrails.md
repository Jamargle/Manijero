# Acceptance record: input_guardrails

- Verdict: accept (independent validator, 2026-11-07). Spec: [input_guardrails.md](../specs/input_guardrails.md); evidence: [appendix](../specs/input_guardrails.appendix.md). No owner walkthrough (owner decision 8).

## Checks rerun

- `./scripts/init.sh --feature input_guardrails`: 2208 passed, 5 skipped (both published lines).
- `CI=true ./scripts/init.sh --fast`: 10 offline checks passed (backend, harness, contract examples, retrieval, generation, abstention, clarification, land-safety).
- `--verify` not rerun: diff touches only `backend/`, docs and `feature_list.json`, no `shared/`, apps, Gradle, or packaging.
- Mutation spot-check (`screen_question` always `None`): not runnable in the validator sandbox (no edit/sed rights). The suite asserts per-case labels, the route-level screened responses, and the privacy no-trace checks, so a constant-`None` would fail them by construction; this is review judgment, not a run.

## Review

- Privacy: `personal_data` hit skips `retain_if_opted_in`, finishes the trace with `withhold_text=True`, and adds only `abstentions_total{reason}`; the reply never echoes the question. Test asserts store rows, trace, log, `/metrics` and response.
- False positives: SIGPAC and cadastral references masked before ID patterns; phone look-arounds skip SIGPAC groups; injection needs verb plus target; out-of-domain needs off-topic marker and no domain term. Fixtures cover eval questions of the repo.
- Copy: three pinned messages match the spec, validated by the abstention copy tests.
- Docs: constraint, ARCHITECTURE, pilot-privacy, backend README, risks, known-limitations updated as specified.

## Limits that remain

- Lexical, Spanish and English only; names and addresses not screened; out-of-domain fires only on listed topics (see known-limitations).
