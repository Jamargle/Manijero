# Acceptance record: `semantic_grounding_judge`

- Spec: [docs/specs/semantic_grounding_judge.md](../specs/semantic_grounding_judge.md); evidence: [appendix](../specs/semantic_grounding_judge.appendix.md).
- Validator run: 2026-11-08, independent of the implementer; no Ollama, no network, no commit.
- Verdict: **accept, condition `pending owner walkthrough`** (scenario 10). Keep status `passing` until the owner reports the walkthrough matched the guide, then persist `accepted`.

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

## Remaining limits (only the owner walkthrough can show)

- Setup downloads the pinned model, verifies the digest, and a second run downloads nothing.
- The report runs end to end against real Ollama and prints the expected `Result:` line.
- The closed-Ollama prerequisite failure reads plainly and recovers.
- Aggregate counts from that run: _to be recorded here, labelled unchecked against human review_.
- The judge's real per-sentence behaviour is unmeasured; its scores make no accuracy claim.
