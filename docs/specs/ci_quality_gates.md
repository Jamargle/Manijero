# Feature Spec: `ci_quality_gates`

## Source metadata

- **Feature:** `ci_quality_gates` — Block pull requests when agreed evaluation metrics regress (`testing`).
- **Depends on:** `evaluation_metrics_report` (accepted). **Status at planning:** `not_started`.
- **User-visible behavior:** no app screen, route, copy, `/ask`, contract, owner command, or owner guide. A developer check inside `./scripts/init.sh --verify` compares today's deterministic retrieval and abstention metrics against a committed, owner-reviewed baseline and fails the tier with one plain `Result:` line when hit@k or abstention correctness drops, or MRR falls below the baseline.
- **Verification:** offline pytest with synthetic baselines, blocked sockets, and the real fixtures/sample read-only; one real check over the existing fixtures and the reviewed 17-case sample; one `./scripts/init.sh --verify` run to prove the tier wiring and its cost.
- **Owner decisions, 2026-11-10 (final, verbatim; the list's duplicate numbers are normalized to 1–6; do not reopen):**
  1. No GitHub Actions job and no branch-protection change. The comparison runs inside `./scripts/init.sh --verify` only.
  2. Compare deterministic fixture metrics against a committed, owner-reviewed baseline: block when hit@k or abstention correctness drops, or MRR regresses beyond 0.
  3. Reports never treat unpublished metadata as authoritative: reviews are read-only metadata, never auto-applied, and the committed baseline is reviewed by the owner before it becomes a gate.
  4. Use only the existing test fixtures and the reviewed 17-case sample in the comparison; approved golden/trap deltas and judge scores are report-only, never blocking (the safety-evaluation constraint forbids an unmeasured gate).
  5. Read-only; deterministic; no live service, no model download, no spend.
  6. Independent validator accept is final; no owner walkthrough.

## Goal

Make an unintended retrieval or abstention regression visible before it merges, using the metric rules the owner already agreed and a baseline a person reviewed. The check uses only offline fixtures and the reviewed 17-case sample, so it adds a few seconds to the release-shaped gate and needs no service, model, or spend.

## Non-goals

- A GitHub Actions workflow change, a new job, branch-protection edits, or a hosted evaluation service.
- Running the grounding judge, downloading a model, calling `/ask` over HTTP, or spending anything. No change to `/ask`, retrieval, thresholds, abstention, or the corpus.
- Making golden-set, trap-set, numeric/date, clarification, or faithfulness numbers blocking; auto-updating or self-healing the baseline; applying any review or approval automatically.
- Gating on `--fast` or any other mode; treating an unreviewed or stale baseline's numbers as a gate.
- A quality claim. The gate proves "these agreed numbers did not get worse", nothing about legal correctness or real-user accuracy.

## Job story

When I change retrieval, the corpus, the glossary, or an answer path the reviewed sample exercises, I want the release-shaped gate to tell me in one line that hit@k, abstention, or MRR got worse against a reviewed baseline, so an unintended regression cannot merge unnoticed and an intentional one requires a reviewed baseline change.

## Acceptance scenarios

### 1. Unchanged inputs pass with one line

Given the committed baseline and unchanged fixtures, reviewed sample, and corpus · When `./scripts/init.sh --verify` (or `check_quality_gate.py check`) runs · Then it measures both fixture groups and the 17 reviewed cases once, prints exactly one line `Result: quality gate passed: fixtures <h1>/7 hit@1, <h3>/7 hit@3, <h5>/7 hit@5, MRR <v>; fixtures abstention <c>/10; reviewed sample <h1>/12 hit@1, <h3>/12 hit@3, <h5>/12 hit@5, MRR <v>; reviewed sample abstention <c>/5. Baseline reviewed by <reviewer> on <date>.`, exits `0`, and writes nothing. Values are the baseline's; a group with no cases renders `n/a` and enforces nothing.

### 2. Each agreed rule blocks on any drop

Given a baseline whose counts or MRR are higher than the current run · When the check compares · Then it exits `1` and names every drop in one line, e.g. `Result: quality gate failed: reviewed sample hit@1 fell from 9/12 to 8/12; reviewed sample MRR fell from 0.8611 to 0.8610. A developer must review the change; if the new numbers are right, the owner reviews and records a new baseline.`
- one fewer hit at hit@1, hit@3, or hit@5 blocks, even when the other k values are unchanged;
- one fewer correctly handled line in the abstention fixture, or one fewer correctly abstained reviewed case, blocks;
- MRR blocks on any fall, including `0.8611` to `0.8610` (zero tolerance on 4-decimal values).

Only group, metric, and counts appear; no question, answer, passage, or path text. The baseline, fixtures, and `knowledge/` stay unchanged.

### 3. Improvements pass and never rewrite the baseline

Given current numbers above the baseline · When the check runs · Then it exits `0`, the line reports the current values, and the committed baseline is untouched. Tightening the baseline is an explicit human `record`, never automatic.

### 4. Only a reviewed, current baseline can gate

- Given a baseline whose review block is missing, empty, or lacks reviewer/date/reason · Then the check prints one `Result: quality gate not enforced: ...` line, exits `2`, and compares nothing.
- Given an unreadable or schema-invalid baseline · Then `baseline_invalid`, exit `2`, no comparison.
- Given a changed fixture/case digest, `as_of`, campaign, `k`, retrieval mode, drafting mode, or glossary setting · Then `baseline_stale`, exit `2`, no comparison.
- Given an `/ask` failure or an unexpected error · Then `ask_failed` or `internal_error`, exit `2`, one fixed line, no traceback on stdout.

### 5. A human records a new baseline; nothing auto-applies

Given a failing or intentionally changed run · When `check_quality_gate.py record --reviewer "<name>" --reason "<text>" [--reviewed-on <date>]` runs · Then it recomputes, prints one line per changed metric (`old -> new`) and one `Result:` line, and writes `backend/config/quality_gate_baseline.json` canonically (sorted keys, 2-space indent, atomic); `--reviewed-on` defaults to today. It refuses with one `Result: baseline not recorded: ...` line and exit `2` when the reviewer or reason is empty, and refuses to record any drop without `--accept-regression`. It creates the file when absent (first baseline). The gate never calls `record`; a recorded file gates only once committed. The review block is the only approval the gate reads; no other review field, golden/trap decision, or judge score is consulted.

### 6. Read-only, offline, deterministic

During `check`, sockets are blocked in tests, `knowledge/`, `backend/tests/fixtures/`, and the baseline are byte-identical afterwards, no file is written, the provider/glossary/cache/trace environment keys are removed and restored, the cache is off, and neither golden, trap, nor judge files are read. Two runs on identical inputs print the same line.

### 7. Fits the tiers without slowing `--fast`

Given `./scripts/init.sh --verify` · Then `--fast` completes first, the gate runs once, and the Android/Desktop builds follow; a gate exit `1` or `2` fails the tier before the builds. Given `--fast` alone, any other mode, or a docs-only pull request (which runs only `--fast`) · Then the gate does not run, and a non-docs change that leaves the metric inputs and values identical prints the scenario-1 pass line. `.github/workflows/gate.yml` and branch protection are unchanged; a non-docs pull request runs the existing `full` job, whose `--verify` now includes the gate.

## Technical approach

- **Fixtures group** — import the accepted `backend/scripts/evaluate_retrieval.py` (`load_eval_questions`, `evaluate`) over `backend/tests/fixtures/retrieval` (7 questions) for hit@1/3/5 and MRR, and `evaluate_abstention.py` (`load_eval_lines`, `evaluate_line`) over `backend/tests/fixtures/abstention` (10 lines) for outcome correctness (each line counts when its outcome equals its `expect`), via `importlib` as `evaluate_metrics` imports `judge_grounding`; never parse stdout. Reuse `eval_metrics.metric_block` so hit@k/MRR mean exactly what the metrics report means.
- **Reviewed group** — one in-process `/ask` run over `knowledge/pac_answer_eval.json` (17 cases: 12 with an expected passage, 5 expected abstentions) with inspection on, mirroring `evaluate_metrics._run_cases`: `create_app`, corpus/as-of/campaign/k overrides, cache off, provider env removed, extractive BM25, glossary off. hit@k/MRR come from `eval_metrics.metric_block` over `eval_metrics.case_row` rows; abstention correctness from `eval_metrics.summarize(rows)["abstention"]["overall"]`. Golden and trap files are not loaded.
- **Baseline** — new committed `backend/config/quality_gate_baseline.json` (`eval-quality-gate-baseline-v1`): settings, input digests, integer counts, 4-decimal MRR, and the review block. SHA-256 pins the six fixture input files (three per group) and `knowledge/pac_answer_eval.json`; the corpus catalog/passages are deliberately not pinned because the gate tests them.
- **Comparison** — same denominators are guaranteed by the digests. Block on `hits_at_k < baseline` for k 1/3/5, `correct < baseline`, or `round(mrr, 4) < baseline`; equality and improvement pass. Report all drops in a fixed order (fixtures, then reviewed; hit@1, hit@3, hit@5, abstention, MRR). Settings are module constants (`as_of` 2026-10-13, campaign 2026, k 5, BM25, extractive, glossary off) that the baseline must record; any mismatch is `baseline_stale`, so `MANIJERO_AS_OF` never changes the result.
- **Authority** — the `review` block must be complete; `baseline_unreviewed`, `baseline_invalid`, `baseline_stale`, `ask_failed`, `internal_error` all exit `2` with one fixed line (`Result: quality gate not enforced: <reason>; a developer must <next step>.`) and no comparison; a regression exits `1`; only a clean pass exits `0`.
- **`scripts/init.sh`** — new `run_quality_gate()` called once from the `--verify|--full)` branch after `run_fast` and before the Gradle full tier, resolving Python like `--backend-tests` and failing with the `--setup-python` hint when no interpreter can import the app. `--fast`, `usage()`, and `--check` keep their shape except the one-line `--verify` description.
- **Cost** — two tiny fixture passes plus 17 in-process cases; target ≤10 s on the owner's Mac, measured in evidence, well under the builds it precedes.

### Reviewing and updating the baseline

1. The failing line and the `record` output show only group, metric, and old/new counts, so a developer can relay them without answer text.
2. The developer asks the owner whether the drop is acceptable; nothing is written before that answer.
3. After approval, `record --reviewer "<owner>" --reason "<plain reason>" --accept-regression` rewrites the committed JSON; `record` prints the same plain deltas.
4. The developer commits that file with the change. Any later `check` enforces it; deleting the review block makes `check` refuse (`baseline_unreviewed`) instead of passing silently.

The first baseline records the owner's 2026-11-10 decision as its review block (`reviewed_by: "owner"`, `reviewed_on: "2026-11-10"`, the rule above as reason); its measured numbers are recorded in the appendix evidence. The implementer must not invent another reviewer and must not change that block later without a new explicit `record`.

### Baseline shape

```json
{
  "schema_version": "eval-quality-gate-baseline-v1",
  "review": {"reviewed_by": "<person>", "reviewed_on": "<date>", "reason": "<why>"},
  "settings": {"as_of": "2026-10-13", "active_campaign": "2026", "k": 5,
               "retrieval": "bm25", "drafting": "extractive", "glossary": "off"},
  "inputs": {"retrieval_fixture": {"catalog": "<sha256>", "passages": "<sha256>", "questions": "<sha256>"},
             "abstention_fixture": {"catalog": "<sha256>", "passages": "<sha256>", "questions": "<sha256>"},
             "reviewed_sample": {"cases": "<sha256>"}},
  "metrics": {"fixtures_retrieval": {"questions": 7, "hits_at_1": 0, "hits_at_3": 0, "hits_at_5": 0, "mrr": 0.0},
              "fixtures_abstention": {"questions": 10, "correct": 0},
              "reviewed_retrieval": {"questions": 12, "hits_at_1": 0, "hits_at_3": 0, "hits_at_5": 0, "mrr": 0.0},
              "reviewed_abstention": {"expected": 5, "correct": 0}}
}
```

The zeros and placeholders show the shape only; `record` writes the measured values.

## Expected file changes

- Create `backend/app/quality_gate.py` — baseline schema/loading/review checks, digest checks, comparison, result lines, canonical JSON.
- Create `backend/scripts/check_quality_gate.py` — `check` and `record` commands, in-process `/ask` run, fixture evaluation, environment isolation.
- Create `backend/config/quality_gate_baseline.json` — the committed, reviewed baseline.
- Create `backend/tests/test_quality_gate.py`, `backend/tests/test_check_quality_gate_command.py`.
- Update `scripts/init.sh` — `run_quality_gate()` in the `--verify` branch and the one-line tier description.
- Update `backend/README.md` (≤30 lines), `ARCHITECTURE.md` (one bullet), `docs/constraints/answers-and-knowledge.md` (Safety evaluation MUST), `docs/risks-and-open-questions.md` (one risk row).
- Do not change: `.github/workflows/gate.yml`, branch protection, `backend/app/eval_metrics.py`, `backend/scripts/evaluate_metrics.py`, `answer_eval`, `golden_set`, `trap_set`, `grounding_judge`, `/ask`, `contracts/`, `knowledge/`, fixtures, or requirements.
- Implementer/validator only after evidence: `feature_list.json` status, `PROGRESS.md`, `docs/progress/*`, `docs/validations/ci_quality_gates.md`.

## Visual design impact

None. Terminal output only.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one bullet: `quality_gate.py`/`check_quality_gate.py` is the developer-only gate in `--verify` over fixture metrics and the reviewed sample, read-only against a committed reviewed baseline, never on the `/ask` path.
- `docs/constraints/answers-and-knowledge.md` "Safety evaluation": update — MUST: only the committed, owner-reviewed baseline over the existing fixtures and the reviewed sample may gate; hit@k and abstention correctness are zero-tolerance and MRR may not fall; golden/trap, numeric, and judge numbers never block; the gate never writes or auto-applies a baseline, and an unreviewed or stale baseline fails closed without comparing.
- `AGENTS.md` and `docs/owner-guide/`: not needed — no workflow, startup, or command name changes, and no owner command or walkthrough; the owner reviews the printed plain deltas and the committed diff.
- `backend/README.md`: update (≤30 lines) — the check, the `record` procedure, and the review rule.
- `docs/risks-and-open-questions.md`: update one row — the gate's numbers rest on synthetic fixtures and the author-reviewed 17-case sample, so it catches retrieval/abstention regressions, not legal or real-user accuracy.
- `PROGRESS.md` and `docs/progress/*` at acceptance: the "all metrics are report-only" limitation becomes "the metrics report stays report-only; the reviewed baseline gate in `--verify` blocks only hit@k/abstention/MRR".

## Focused verification

Runs from the repository root; needs the backend environment (`./scripts/init.sh --setup-python`) but no Ollama, network, or service.

<!-- verify:start -->
```sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_quality_gate.py tests/test_check_quality_gate_command.py -q
py="${MANIJERO_PYTHON:-backend/.venv/bin/python}"
out="$("$py" backend/scripts/check_quality_gate.py check)"; printf '%s\n' "$out" | tail -n 1; printf '%s\n' "$out" | grep -q '^Result: quality gate passed'
test "$(printf '%s\n' "$out" | wc -l | tr -d ' ')" = "1"
git diff --quiet -- knowledge/ backend/tests/fixtures/ backend/config/quality_gate_baseline.json
```
<!-- verify:end -->

## Appendix

See [`ci_quality_gates.appendix.md`](ci_quality_gates.appendix.md) for repository research, the ordered plan, tests by behavior, evidence to capture, and the validator checklist.
