# `backend_container_image` acceptance

## Verdict

**Accepted** on 2026-11-01. The independent validator accepted everything except the operations.md owner
walkthrough, which the owner then ran personally on 2026-11-01; a second validator pass accepted the recorded
walkthrough evidence.

## Independent verification

- Validator: focused block (170 passed, 2 skipped) and `--fast` (all 9 checks) passed with a fake Docker CLI,
  fake probes, and fake Ollama; the implementer's `--verify` passed with Gradle's JDK as `JAVA_HOME`. Spot
  checks covered the run arguments, the Dockerfile, the allowlist, the relay, and unchanged service code
  ([appendix checklist](../specs/backend_container_image.appendix.md#validator-checklist)).
- Owner walkthrough steps 1–10 ([owner guide](../owner-guide.md#owner-walkthrough-container)) on the owner's Mac,
  Docker Desktop 4.97.0 (244584), from `integration/2026-11-01-batch-3` (this branch unchanged since `8f2d03c`):
  the owner confirmed every step matched the guide, including the missing-prerequisite case (Docker Desktop
  closed) and the recovery (Ollama quit, then reopened). First build about 2–3 minutes, image 5.6 GB, no NVIDIA
  package in the build log; the status `OK  Drafting` line is checked from inside the container, so the relay
  reached host Ollama. Detail in the appendix "Feature evidence".

## Limits

- Walked through on one Apple-silicon Mac only; individual `Result:` lines were not sent, only the owner's
  confirmation that each matched the guide.
- No app question was sent to the container; app end-to-end use is `local_end_to_end_smoke`. No answer-quality claim.
- Loopback only (`127.0.0.1:8000`). Images (about 5.6 GB each) are never pruned. The guide's "10 to 30 minutes"
  first-build estimate is kept as an upper bound; the measured build was faster.
