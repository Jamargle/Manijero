# answer_deadline_notices — appendix

## Repository research

### Files inspected

- `feature_list.json` — feature row: backend, depends on `backend_campaign_validity` and
  `backend_citation_hardening`, both accepted. The selector was not run (no shell in the
  planning session); the parent supplied the feature id and role.
- `PROGRESS.md` "Current state" — corpus is four sources and four passages; numeric check accepted.
- `docs/specs/numeric_grounding_check.md` — its non-goal names this feature. `verify_draft`
  rejects unsupported written dates, so notices must be added after verification.
- `docs/specs/backend_campaign_validity.md` — `as_of` is the route-injected UTC date
  (`ask_api.get_as_of_date`). Expired *sources* are rotated out of the runtime catalog, so this
  feature only covers a passed deadline *inside* a still-valid source (`valid_until` 2026-12-31).
- `backend/app/ask_api.py` — `_answer` passes `as_of` to `answer_with_clarification`;
  `AskResponse.answer` has `max_length=1200`; an invalid passage set becomes the generic 503.
- `backend/app/generation.py` — `generate_grounded_answer` verifies, then `_fit_claims` /
  `_assemble_claims` build `LEAD_IN body NOTICE` and renumber markers; `verify_draft` checks
  only `claims[0]` against the 1200 bound, with no `as_of`.
- `backend/app/retrieval.py` — `PASSAGE_OPTIONAL_KEYS`, `_PassageSetValidator`, `_build_record`,
  `RetrievedPassage` (retrieval-local fields never reach `AnswerSource`).
- `backend/app/abstention.py` — pinned abstention copy (tone reference: `tú`, next step,
  cooperative named); `answer_or_abstain` returns `Answered` unchanged.
- `backend/app/gemini_generation.py` — `parse_draft` rejects `NOTICE`/`LEAD_IN` as
  `output_code_owned_text`; `local_generation.py` imports it.
- `backend/app/answer_eval.py` — evaluation checks `critical_facts` by substring in the answer,
  so a notice date could turn a missing fact into a match (see risks).
- `backend/app/land_safety_eval.py` — digit checks apply to abstention messages only.
- `backend/app/embedding_index.py` — records `passages_sha256`, so editing `passages.json` makes
  an existing local embedding index stale (hybrid falls back to BM25 until rebuilt).
- `knowledge/passages.json`, `passages.schema.json`, `source_catalog.json` — the two deadline
  passages (`dl_1_2026`: "hasta el 15 de mayo de 2026"; `rd_537_2026`: "finalizará el 15 de
  junio", campaign 2026).
- `shared/.../chat/CitationPresentation.kt`, `ChatTranscript.kt` — the answer text is kept
  verbatim (newlines included). Markers must be exactly `1..n`; the paragraph has none.
- `contracts/openapi.yaml` — `answer` is a free string up to 1200; no change needed.
- `scripts/init.sh` — `--feature` reads the spec's verify block; no registration needed.
- `DESIGN.md` "Design intent", `CONTEXT.md` scope — copy tone; cooperative is a named contact.

### Existing patterns to follow

- Code-owned pinned strings as module constants with tests pinning them (`NOTICE`,
  `ABSTENTION_MESSAGES`).
- Optional passage key pattern: `critical` (validator plus schema plus schema-sync test in
  `test_retrieval.py`).
- Verify-then-assemble: nothing added after `verify_draft` comes from a generator.

### Current gaps

- No passage carries a structured deadline; answers never state whether a cited deadline passed.
- The answer budget is tight. `dl_1_2026`'s excerpt is about 870 characters, so it alone is about
  1020 with lead-in and notice. The worst-case paragraph (one `EXPIRED` + `COOPERATIVE`, about
  155 characters plus `\n\n`) leaves an estimated margin of about 25 characters. Measure it in
  step 1.

## Implementation plan

1. Baseline: run the evaluation command (contract line 3) and record its aggregates. Compute
   `len(answer)` for `pasaje-plazo-presentacion-2026-andalucia` alone plus the worst-case
   paragraph. If it exceeds 1200, stop and report a blocker; do not shorten other pinned copy.
2. `deadline_notices.py`: constants, month table, `format_spanish_date`, `deadline_paragraph`
   (dedupe, sort, strict `<` against `as_of`, `None` → cooperative only), `CODE_OWNED_MARKERS`.
3. `retrieval.py`: optional key, ISO real-date validation with a fixed rule string, record
   and `RetrievedPassage` field (default `None`, last).
4. `passages.schema.json`: `official_deadline` property (isoDate pattern, description:
   inclusive last day, reviewed, never inferred).
5. `generation.py`: pass the rank→passage map and `as_of` into `_fit_claims`, then append the
   paragraph and recompute it for each kept set. The empty fit result stays the existing
   `answer_too_long` path. Update the docstring rule.
6. `gemini_generation.py`: extend the code-owned check with `CODE_OWNED_MARKERS`.
7. `knowledge/passages.json`: add `"official_deadline"` to the two passages (values in
   scenario 8), read from each excerpt and the source's campaign.
8. Tests: `test_deadline_notices.py` covers formatting for all 12 months and day 1, the
   boundary day, dedupe and order, `None` as-of, no metadata, uncited deadline, fit drop and
   recompute, first claim too long, and validator rejections. `test_retrieval.py` covers the
   schema sync and the key on `RetrievedPassage`. `test_pac_corpus.py` covers the real values,
   the day–month present in the excerpt, the year equal to the campaign, and the real-corpus
   budget. `test_generation.py` covers verify-before-append (scenario 6) and unchanged answers
   without metadata. `test_gemini_generation.py` and `test_local_generation.py` cover
   code-owned rejection, the fallback answer carrying the paragraph once, and the existing
   `count(NOTICE) == 1` assertions still holding. `test_ask_endpoint.py` covers `/ask` with an
   injected `as_of` before and after 2026-05-15, abstention and clarification without a
   notice, unchanged keys, and an invalid `official_deadline` returning 503.
9. Fix existing real-corpus assertions that assumed the answer ends with `NOTICE` only where
   the cited passage now has a deadline; never weaken a check to make it pass.
10. Run the focused block; compare aggregates with step 1.
11. Docs per the contract's durable documentation list.

## Verification plan

- `./scripts/init.sh --feature answer_deadline_notices` runs all four lines with exit `0`.
- The evaluation's state, source, and passage aggregates match the step 1 baseline. Also
  compare critical facts. A change there is reported per case, stating whether the matched fact
  came from the notice paragraph, because the evaluator matches by substring.
- Mutation spot-check (by hand, not committed): make `deadline_paragraph` return `""`, then make
  the expiry comparison `<=`. Scenarios 1–3 and the boundary test must fail.
- E2E: not needed. There is no client, route, or contract change. `/ask` is covered in-process
  by `test_ask_endpoint.py`, and the client renders answer text verbatim.
- Live model: not run; Gemini has no transport and local drafting is fixture-faked.

## Evidence to capture

- Step 1 budget measurement (characters) and the baseline and post-change aggregates, one line
  each.
- The focused-block result, one line per command, with pass counts.
- The mutation spot-check result, in one line.
- The two `official_deadline` values and how each was confirmed against its excerpt.
- The doc files edited, one line each.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-03 (implementer)
- Budget (step 1): `pasaje-plazo-presentacion-2026-andalucia` alone = 1014 chars; +`\n\n`+worst-case paragraph (septiembre) = 1176 <= 1200, fits (24 spare). Other passage 684.
- Baseline vs after, `evaluate_pac_answers.py --as-of 2026-10-31` (baseline = same code with HEAD `passages.json`, i.e. no deadlines): output byte-identical (`diff` empty). 14 cases, 11 answered, 13 state agree, 9 critical facts, 8 source agree, 1 unexpected answer; no per-case difference.
- `./scripts/init.sh --feature answer_deadline_notices`: passed (contract examples ok; touched suites; evaluation exit 0; full backend 1913 passed, 4 skipped).
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend-tests 1913 passed, 4 skipped; harness-tests 20 passed).
- Mutation spot-check (by hand, reverted): `deadline < as_of` -> `<=` failed the boundary test; `deadline_paragraph` returning `""` failed 10 tests.
- Values: `pasaje-plazo-presentacion-2026-andalucia` = 2026-05-15 (excerpt: "hasta el 15 de mayo de 2026", source `dl_1_2026` campaign 2026); `pasaje-plazo-modificacion-2026-andalucia` = 2026-06-15 (excerpt: "finalizará el 15 de junio, inclusive", source `rd_537_2026` campaign 2026); asserted by `test_pac_corpus.py` (day-month in excerpt, year = campaign).
- Docs edited: `docs/constraints/answers-and-knowledge.md` (one MUST), `knowledge/README.md` (field row), `backend/README.md` (one paragraph). `known-limitations.md` line left for acceptance, per the spec.
- Not run: `--verify` (no Android/Desktop/Gradle change); Gemini/local transports are faked.

## Validator checklist

- [ ] Changes are limited to the contract's expected files and docs (`git diff --stat`); no
      `contracts/`, `shared/`, `verify_draft`, `extract_*`, or abstention-copy change.
- [ ] Both sentences match the contract byte for byte. The date has no leading zero and a
      lowercase month. The paragraph follows `"\n\n"` and contains no `[n]`.
- [ ] Expiry uses strict `official_deadline < as_of`, with `as_of` from the route dependency;
      no clock read in `deadline_notices.py`.
- [ ] No runtime code parses dates from passage or claim text for notices; only
      `official_deadline` drives them.
- [ ] Abstentions and clarifications are byte-identical to before; uncited deadline passages add
      nothing.
- [ ] A model draft containing notice text is rejected and falls back; the final answer has the
      paragraph exactly once.
- [ ] The 1200 bound holds with the paragraph; the real-corpus budget test exists and passes.
- [ ] `official_deadline` is in schema and validator, and the sync test passes. The real values
      match the excerpts (15 de mayo de 2026; 15 de junio with campaign 2026).
- [ ] Each of scenarios 1–9 maps to a named passing test. The evaluation comparison is
      recorded, and any difference is explained.
- [ ] The focused block runs unchanged through `./scripts/init.sh --feature
      answer_deadline_notices`.
- [ ] Durable doc edits match the contract without restating other files. `feature_list.json`
      and `PROGRESS.md` are updated only at acceptance. Validator accept is final (owner
      decision 6).
