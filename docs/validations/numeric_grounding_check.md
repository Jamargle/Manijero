# `numeric_grounding_check` acceptance

## Verdict

**Accepted** on 2026-11-01 after independent validation. No revise round was needed.
Spec: [`numeric_grounding_check.md`](../specs/numeric_grounding_check.md); implementer evidence and
scenario-to-test map: [appendix](../specs/numeric_grounding_check.appendix.md) "Feature evidence".

## Independent verification

- `./scripts/init.sh --feature numeric_grounding_check` passed (exit 0): the three published
  lines run unchanged; the full backend suite gave **1446 passed, 4 skipped**.
- `evaluate_pac_answers.py` (line 2 of the block) exits 0 with aggregates equal to the recorded
  baseline: 14 cases, 13 state agreement, 11 answered, 11 expected-answer coverage, 8 source
  agreement, 9 critical facts, 3 abstentions, 1 unexpected answer.
- `CI=true ./scripts/init.sh --fast`: 8 of 9 checks ok (contract-examples, backend-tests,
  source-catalog, retrieval MRR 0.857, generation, abstention, clarification, land-safety, each 0
  misses). `gradle-jvm-test` failed only with "Unable to locate a Java Runtime"; this host has no
  JDK. It does not matter here: the diff touches no Kotlin, Gradle, `shared/`, `androidApp/`, or
  `desktopApp/` file, and the feature is backend-only. `--verify` was not rerun for the same reason.
- Diff review: changes are confined to `backend/app/generation.py`, three backend test or fixture
  files, and the listed docs. No new import or dependency, no network or model call. The new rule
  is one `elif` after the digit rule in `verify_draft`, so it only adds rejections, yields at most
  one numeric code per claim (`figure_unsupported` wins), and uses a fixed content-free detail.
  `extract_figures`, `gemini_generation.py`, `local_generation.py`, `contracts/`, `knowledge/`
  data, and `scripts/init.sh` are untouched. A failed check reuses the existing
  `verifier_rejected` -> extractive-baseline path, never an unverified draft.
- Ad hoc probes of `extract_numeric_facts` agree with the spec table: "quince (15) días hábiles"
  -> `dur:15:dia:habiles`; "treinta y uno de mayo" -> `dm:31-5`; "una vez al año" -> no fact;
  "15 de mayo de 2031" -> `d:`, `dm:`, `m:`.
- Scenario tests exist for 1-9 (named in the appendix); scenario 8 asserts no socket opened and no
  draft text (`mayo`) in the log. The implementer's mutation spot-check (18 failures with the rule
  disabled) was reviewed for consistency, not rerun.

## Accepted scope and remaining limits

- The check is lexical and Spanish-only, covers only day/week/month/year durations and `por
  ciento`, and rejects some correct paraphrases (ranges, an added year). Recorded in
  [`known-limitations.md`](../progress/known-limitations.md).
- Not measured: the effect on the live local model's verified-draft rate (needs Ollama, out of
  scope for this run). No semantic judge or numeric-accuracy metric is claimed.
- Durable docs updated as specified: `docs/constraints/answers-and-knowledge.md`,
  `knowledge/README.md`, `backend/README.md`, `docs/risks-and-open-questions.md`,
  `docs/progress/known-limitations.md`. `PROGRESS.md` and the session-log pointer are left for the
  orchestrator at acceptance.

## Recommended state update

Set `numeric_grounding_check` to `accepted` in `feature_list.json`, move the appendix to
`docs/archive/specs/` per repo convention, and add one pointer line to
`docs/progress/session-log.md`.
