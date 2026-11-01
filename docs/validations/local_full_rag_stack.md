# `local_full_rag_stack` acceptance

## Verdict

**Accepted** on 2026-11-01. The independent validator accepted everything except the
operations.md owner walkthrough, which the owner then ran personally on 2026-11-01 and which passed.

## Independent verification

- Validator: focused block, `--fast`, `--verify` (with Gradle's JDK as `JAVA_HOME`), and the checklist in the
  [appendix](../specs/local_full_rag_stack.appendix.md#validator-checklist) passed, all with fakes and temporary homes.
- Owner walkthrough steps 1–9 ([owner guide](../owner-guide.md)) on the owner's Mac: setup check all ready;
  start refused with Ollama closed and named the fix; start with Ollama open used hybrid search, release
  `3050d1b8b5e10f82`, and the pinned Mistral drafting model; the service survived closing Terminal and a re-run
  started nothing new; status was all OK; recovery: quitting Ollama turned only Drafting into `PROBLEM` and
  reopening it returned all OK without a restart; stop, repeated stop, and status after stop gave the documented
  lines. Step lines are in the appendix "Feature evidence".

## Limits

- Walked through on one Mac only, with the setup from `local_rag_bootstrap` already complete.
- No app question was sent to the running service during the walkthrough; app end-to-end use is
  `local_end_to_end_smoke`. No answer-quality claim.
- Loopback only (`127.0.0.1:8000`); physical devices and other machines cannot reach it.
