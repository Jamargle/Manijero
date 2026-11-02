# Acceptance record: answer_deadline_notices

Verdict: **accept** (validator, final; no owner walkthrough per spec decision 6).
Spec: [answer_deadline_notices.md](../specs/answer_deadline_notices.md) · Evidence: [appendix](../specs/answer_deadline_notices.appendix.md).

## Checks rerun
- `./scripts/init.sh --feature answer_deadline_notices`: passed (4 lines; 1913 passed, 4 skipped).
- `./scripts/init.sh --fast`: passed (10 offline checks; retrieval MRR 0.857; generation, abstention, clarification, land-safety 0 differing).
- `--verify` not rerun: the diff touches only `backend/`, `knowledge/`, and docs, no `shared/`, apps, or Gradle.

## Findings checked by reading code
- Dates: `pasaje-plazo-presentacion-2026-andalucia` = 2026-05-15 (text: "hasta el 15 de mayo de 2026", source dl_1_2026, campaign 2026); `pasaje-plazo-modificacion-2026-andalucia` = 2026-06-15 (text: "finalizará el 15 de junio, inclusive", source rd_537_2026, campaign 2026). No other passage has the key.
- Never model-written: `deadline_paragraph` is code-only from reviewed metadata; `parse_draft` rejects `CODE_OWNED_MARKERS` (normalized, accent/case-insensitive), covering the local provider.
- Position: `verify_draft` runs at generation.py:1096, `_fit_claims` appends the paragraph afterward; abstain and `NotAnswered` paths return before it, and clarification is decided earlier.
- Expiry: `deadline < as_of` (strict), so the last day stays open; `as_of=None` gives cooperative only; `as_of` is the injected UTC date from `get_as_of_date`, the one campaign validity uses.
- Bound: paragraph recomputed per kept-claim set inside the 1200 loop; first claim that cannot fit abstains.
- Non-goals respected: no `contracts/`, `shared/`, or app changes.

## Limits that remain
- Only two hand-entered deadlines exist; indexes built earlier serve answers without notices until rebuilt (record in known-limitations.md at persistence).
