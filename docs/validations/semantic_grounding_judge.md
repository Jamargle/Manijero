# Acceptance record: `semantic_grounding_judge`

- Spec: [docs/specs/semantic_grounding_judge.md](../specs/semantic_grounding_judge.md); evidence: [appendix](../specs/semantic_grounding_judge.appendix.md).
- Validator run: 2026-11-08, independent of the implementer; no Ollama, no network, no commit.
- Verdict: **accept, condition `pending owner walkthrough`** (scenario 10), met 2026-11-08: status `accepted`.

## Checks rerun

- `./scripts/init.sh --feature semantic_grounding_judge`: `270 passed`; `check-record`: judge record valid and pinned, different tag, digest, and family from the generator.
- `CI=true ./scripts/init.sh --fast`: all 10 checks passed (`backend-tests 3017 passed, 9 skipped`, `harness-tests 20 passed`).
- `--verify` not rerun: the diff touches no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging files.

## Inspected

- Judge record `backend/config/grounding_judge_model.json` matches the Handoff pin exactly (tag, digest, size, 7.6B, Q4_K_M, Apache-2.0, license sha256 and 11343 chars, Ollama 0.40.14, `recorded_on` 2026-11-08); no invented value.
- `/ask` path (`main.py`, `ask_api.py`, `generation.py`, `gemini_generation.py`, `local_generation.py`), the generator record, `golden_set.json`, `contracts/`, `shared/`, and requirements are unchanged; only `grounding_judge.py` itself mentions the module name.
- Fail-closed: `parse_verdict` accepts only an object with exactly the key `verdict` and one of three values; uncited and invalid citations never reach the judge.
- Labelling: `judge_review: unchecked_against_human_review`, fixed `limits` state no accuracy claim, and the `Result:` line says "unchecked against human review".
- Loopback only: the only base URL is `OLLAMA_BASE_URL`; tests need no Ollama.
- Owner commands: `init.sh` blocks take no arguments, end with one `Result:` line, and name the fix; owner guide has 49 lines and a pinned-line table; `backend/README.md` addition is 25 lines.
- Durable docs updated as listed (ARCHITECTURE, lands and answers constraints, risks row 13, READMEs, owner-guide index).

## Owner walkthrough (scenario 10), 2026-11-08

- The owner followed `docs/owner-guide/grounding-judge.md` and reports every step behaved as the guide expects.
- Setup runs and the closed-Ollama (`ollama_unavailable`) prerequisite and recovery: reported "as expected"; their `Result:` lines were not quoted.
- Report `Result:` line as reported: `judged 29 draft sentences from 28 drafts (28 supported, 1 not supported, 0 unclear, 1 not judged); judge scores are unchecked against human review.` Report path `build/grounding-judge/report.json` in the owner's worktree.
- These counts are judge scores, unchecked against human review; no accuracy claim is made about the judge.
- The model-card link in `license_reference` was not read from Ollama and not confirmed by the owner; the record now says so (focused tier rerun: passed).

## Remaining limits

- The judge's real per-sentence behaviour is unmeasured against human review; its scores make no accuracy claim.
- The judge ran on the owner's Mac only; one walkthrough run, not a repeatability study.
