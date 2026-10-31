# `legal_change_impact_analysis` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

## Implementation plan

1. Inspect the current owning modules, schemas, and focused command before changing code.
2. Implement the capability behind a narrow interface with explicit configuration and fail-closed behavior.
3. Add representative and adversarial fixtures, including malformed, stale, duplicate, unavailable, and ambiguous cases as applicable.
4. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

### Implementation

- `backend/app/change_impact.py` (standard library only) is a read-only analyzer
  over the quarantine written by `app/document_ingestion.py`. It loads
  `official-ingestion-state-v1` plus each extracted `official-ingestion-document-v1`,
  re-validates the approved `source-catalog-v1` and `passage-set-v1` with the
  existing validators at `--as-of`, and optionally reads the identity/reference
  fields of a `pac-answer-eval-v1` case set. It never writes `knowledge/`, never
  changes a lifecycle or review status, and never touches the answer path.
- Each candidate gets a `version_status`: `approved_copy` (current bytes equal an
  approved source's content hash), `unchanged_since_ingestion`,
  `new_version` (a previous extracted version differs), `baseline_unknown` (a
  changed or first-seen document with no comparable previous text),
  `no_extracted_document` (ingestion recorded no text), or `analysis_failed`.
- Signals are lexical over extracted text and split by kind
  (`publication`, `amendment`, `repeal`, `validity`). A signal is
  `machine_evident` only with its required detail: `amendment` and `repeal` need
  a named instrument in the same sentence, `validity` needs an explicit Spanish
  calendar date (`d de mes de aaaa` or `dd/mm/aaaa`), and `publication` needs a
  bulletin reference plus a number or explicit date. Sentence-scoped negation,
  `U+FFFD` damage, or a missing detail makes the signal `ambiguous`. Recognised
  negation is limited to the listed phrasings:
  `no se modifica/deroga/suprime/anula/revoca/altera/afecta/publica`,
  `sin que se modifique` (and the other listed verbs, subjunctive included),
  `no supone/implica/conlleva una modificación/derogación`,
  `no queda/quedan derogado/modificado/sin efecto`,
  `no deja/n deja sin efecto`, `no pierde/n su vigencia`, `en ningún caso`,
  `tampoco`, and `nunca`. Any other negative wording is read as positive or
  missed.
- Triggers are broad Spanish word stems, not a legal-action parser:
  `derog*`/`revoc*`/`deja sin efecto`/`queda sin efecto`/`pierde vigencia`
  (repeal), `modific*`/`modifiq*` (including the nouns `modificación` and
  `modificaciones`)/`nueva redacción`/`se suprime|añade|adiciona` (amendment),
  `entra|entrada en vigor`/`prorrog*`/`mantiene su vigencia`/
  `se extiende|amplía|prorroga|reduce … hasta` (validity), and bulletin names/
  `se publica`/`publicado en el` (publication). Consequently a document-part
  heading or a noun phrase is reported rather than ignored: a bare
  "Disposición derogatoria única.", "Modificaciones presupuestarias." or
  "La modificación de las condiciones de acceso se aprueba por resolución."
  produces an `ambiguous` review-requiring signal. Only a document part with no
  trigger word, such as a bare "disposición adicional", emits no signal. A static
  deadline such as "el plazo … se mantiene hasta …" or "la vigencia … hasta …"
  is not a validity signal at all: a changed deadline needs change wording such
  as "se extiende/amplía/prorroga/reduce … hasta", and only then does an explicit
  calendar date make it machine-evident. Every signal carries a page/section
  location and a bounded excerpt of at most 280 characters; a candidate carries at most 50
  signals (up to 50 excerpts), and the separate text diff carries at most five
  changed-block excerpts.
- Linking uses canonical instrument keys (`real decreto 1048/2022`,
  `decreto-ley 1/2026`, `ley organica 3/2018`, `orden 1234/2022`) and document
  identity: an instrument is the candidate's own identity only when the title
  *starts* with that numbered instrument (`own_instrument_key` anchors the match
  at offset 0). An unnumbered title such as "Resolución de 9 de septiembre de
  2099, por la que se modifica la Ley 5/2098" therefore keeps every named
  instrument as a target instead of losing the link. Reported links name the
  affected approved sources, reviewed passages (including passages that cite an
  affected instrument), and reviewed evaluation cases, with the reason for each
  link.
- Review reasons are fixed: `new_version`, `baseline_unknown`,
  `approved_copy_differs`, `affected_source`, `affected_passage`,
  `previous_text_unavailable`, `text_changed_without_signal`,
  `ambiguous_signal`, `conflicting_signals`, `analysis_failed`.
  `review.required` is true exactly when a reason exists, and `review_gate`
  always records `canonical_changes_applied: false`,
  `automatic_retirement: false`, `requires_human_approval: true`. Any ambiguous
  `publication`, `amendment`, `repeal`, or `validity` signal — negated wording
  included — adds `ambiguous_signal` and makes the candidate review-required,
  even when it links no approved source (an unlinked blanket repeal cannot pass
  as "nothing to review"). Negated signals are reported and excluded from
  targeting, but they still require review rather than being dropped. A reviewed
  passage or evaluation case that links a target instrument when no approved
  source carries that instrument adds `affected_passage`, so a potentially
  affected passage or case never leaves `review.required` false.
- A candidate that ingestion failed or rejected is reported as
  `no_extracted_document` with `analysis_failure: "no_extracted_document"`, an
  empty signal list, and no review reason: the report states why no text analysis
  exists instead of leaving the field null, while retrying or fixing the
  ingestion stays owned by the ingestion state (`status`, `failure`, `attempts`).
  A per-candidate analysis failure is isolated under a fixed category and never
  aborts the run: `missing_extracted_document`, `extracted_text_mismatch`,
  `malformed_extracted_document`, `size_limit_exceeded`, `internal_error`.
  Global invalid inputs (catalog, passages, cases, ingestion state, `--as-of`,
  a report path inside `knowledge/`, more than 1,000 candidates) fail closed with
  nothing written. Bounds: 1,000 candidates, 50 signals per candidate, 5,000
  blocks, 2,000,000 characters per document.
- `backend/scripts/analyze_legal_changes.py` is the operator CLI. Exit `0` means
  the report was written and nothing needs review; `1` means the report was
  written with review-required or analysis-failed candidates; `2` means the run
  aborted before writing, printing only a fixed error name to stderr.
- The report has no wall-clock timestamp and is serialized with sorted keys and
  a trailing newline, so identical inputs and `as_of` produce a byte-identical
  file. It embeds the SHA-256 of every input and carries a fixed `limits` list.
  `knowledge/legal-change-impact.schema.json` publishes the
  `legal-change-impact-report-v1` contract.
- `backend/tests/test_change_impact.py` adds 56 focused tests with `backend/tests/fixtures/change_impact/` (approved catalog,
  passages, cases, ingestion state, and quarantine). Regression tests cover an
  unlinked blanket repeal, an unlinked ambiguous validity, a realistic
  `Resolución … por la que se modifica la Ley 5/2098` title, the unchanged
  `Real Decreto 2200/2099 … modifica el Real Decreto 2077/2099` identity,
  `disposición adicional` alone not being an amendment, and a static
  `plazo … hasta` deadline not being a validity signal. After the second
  validator repair pass they also cover a passage, and separately an evaluation
  case, that cites a target instrument with no catalog source
  (`affected_passage` review reason), seven recognised negation phrasings
  (`ambiguous` + `negated_signal`, no target link, review reason
  `ambiguous_signal`), and four broad-stem false-friend phrases
  (`Disposición derogatoria única.`, `Modificaciones presupuestarias.`,
  `La modificación de las condiciones de acceso …`, `La prórroga del convenio …`)
  that stay ambiguous and review-required by design.
- `backend/README.md`, `knowledge/README.md`, `ARCHITECTURE.md`,
  `CONSTRAINTS.md`, `PROGRESS.md`, and `docs/risks-and-open-questions.md`
  document the command, boundary, and limits.

### Verification (2026-10-27, after second validation repair)

```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --backend-tests
# 728 passed, 1 warning in 8.32s
# warning: StarletteDeprecationWarning (httpx/testclient), unrelated to this feature

MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature legal_change_impact_analysis
# 728 passed, 1 warning in 8.56s

./scripts/init.sh --fast
# All 9 offline checks passed.
# Fast tier passed.

cd backend && .venv/bin/python -m pytest tests/test_change_impact.py -q
# 56 passed in 0.78s
```

`./scripts/init.sh --verify` was not run: the change is backend/knowledge-schema
only and does not touch the shared/Android/Desktop surface, packaging, the HTTP
contract, or the answer path.

### Fixture run, reproducibility, and review evidence (2026-10-27, second repair pass)

Two CLI runs over the synthetic fixtures, each to its own temporary report file:

```sh
backend/.venv/bin/python backend/scripts/analyze_legal_changes.py \
  --ingestion-state backend/tests/fixtures/change_impact/ingestion-state.json \
  --quarantine backend/tests/fixtures/change_impact/quarantine \
  --catalog backend/tests/fixtures/change_impact/catalog.json \
  --passages backend/tests/fixtures/change_impact/passages.json \
  --cases backend/tests/fixtures/change_impact/cases.json \
  --as-of 2026-10-27 --report "$TMP/report-1.json"
# exit 1 (both runs)
```

Result: both runs exited `1` and the two files were byte-identical
(`sha256 80124959df903669186934a6e620494c0e7bc34027443682ad8e69701cbdc2be`).
Only the `limits` strings changed in this pass; the candidate set, signals,
review reasons, and summary counts are unchanged from the previous record. The
earlier digest is obsolete because `limits` is part of the report.

```text
candidates: 5   new_version: 2   approved_copy: 1   no_extracted_document: 1
baseline_unknown: 1   unchanged_since_ingestion: 0   analysis_failed: 0
machine_evident_signals: 7   ambiguous_signals: 1
review_required: 3   affected_sources: 3   affected_passages: 3
affected_evaluation_cases: 2
review_gate: canonical_changes_applied=false automatic_retirement=false
             requires_human_approval=true
```

| Candidate (prefix) | Fixture role | `version_status` | `analysis_failure` | Review reasons |
|---|---|---|---|---|
| `7825dfd2` | amending `Real Decreto 2200/2099` | `new_version` | none | `new_version`, `affected_source` |
| `6fe24ce6` | `Decreto-ley 2/2099` with an ambiguous repeal | `new_version` | none | `new_version`, `approved_copy_differs`, `affected_source`, `ambiguous_signal` |
| `969726a9` | baseline-unknown `Ley 5/2098` change | `baseline_unknown` | none | `baseline_unknown`, `affected_source` |
| `2f79016f` | approved copy, no signal | `approved_copy` | none | none |
| `4a71fd58` | ingestion produced no text | `no_extracted_document` | `no_extracted_document` | none |

The machine-evident amendment links `fixture-rd-2077-2099` as
`amendment_target`, then `fixture-pasaje-rd-2077-plazo`, then case
`fixture-caso-plazo-rd`. The ambiguous repeal points at `fixture-dl-2-2099`
with `ambiguous_signal` and no retirement. The baseline-unknown change links the
cross-referencing passage `fixture-pasaje-dl-2-2099-plazo` and case
`fixture-caso-cambios-ley`.

`test_analysis_never_changes_canonical_knowledge` hashes every file under the
fixture input tree (catalog, passages, cases, ingestion state, and quarantine
documents) and every file under `knowledge/` before and after two runs plus a
report write, and asserts both trees are byte-identical afterwards; it now
detects a write to its own inputs, not only to canonical knowledge. The produced
report validates against `knowledge/legal-change-impact.schema.json` with 0
`Draft202012Validator` errors. Tests also cover seven recognised negation
phrasings across all four signal kinds (publication included) yielding
`ambiguous` + `negated_signal`, no target link, and review reason
`ambiguous_signal`; four broad-stem static phrases staying ambiguous and
review-required; a passage-only and a case-only link to a target instrument with
no catalog source (`affected_passage`); a
publication without a bulletin reference, a validity claim without a calendar
date, an unlinked blanket repeal and an unlinked ambiguous validity forcing
review, a realistic unnumbered `Resolución … por la que se modifica la Ley
5/2098` title still linking the amended instrument, `Real Decreto 2200/2099 …
modifica el Real Decreto 2077/2099` keeping only `2077/2099` as a target,
`disposición adicional` alone not being an amendment, a static `plazo … hasta`
deadline not being a validity signal, conflicting amendment and repeal of one
instrument, changed text with no signal, missing previous text, corrupt digests,
the candidate/signal bounds, unsafe report paths, and all three CLI exit codes.

### Acceptance (2026-10-27, third validation pass)

Independent validation accepted the feature after two `revise` cycles. On the
final pass the validator reran the spec's focused block (728 backend tests), the
fast tier (all nine offline checks), the 56 focused tests, and the fixture CLI
twice with byte-identical output and SHA-256
`80124959df903669186934a6e620494c0e7bc34027443682ad8e69701cbdc2be`; it also
re-probed every closed finding outside the feature tests. `./scripts/init.sh
--verify` was not run because the change touches only the backend,
feature-owned knowledge schema, and docs, not shared/Android/Desktop, packaging,
the HTTP contract, or the answer path. Non-blocking notes (spelled-out bulletin
names only, sentence-scoped negation, and the defensive CLI catch) and the full
acceptance evidence are in
[`docs/validations/legal_change_impact_analysis.md`](../../validations/legal_change_impact_analysis.md).

### Honest limits

- Only synthetic fixtures back this feature. No live run analyzed a real
  published amendment, detection precision/recall is unmeasured, and no claim
  beyond the fixture scope is supported. A change expressed without the expected
  Spanish wording, or only in an image/scanned page, is not detected.
- Detection is lexical over extracted text and says nothing about legal effect.
  Triggers are broad word stems, so a real document's static wording (`entrada en
  vigor`, `prórroga`, `modificación`, a `Disposición derogatoria` heading) usually
  produces an ambiguous signal: review-required may be near-universal, and that
  reviewer load is the price of not silently dropping a legal change. Every
  ambiguous `publication`/`amendment`/`repeal`/`validity` signal, negated wording
  included, becomes a review item — also on an unchanged approved copy whose own
  text carries such wording — and so do a new version, an unknown baseline that
  touches a known source, a passage or case linking a target instrument without
  an approved source (`affected_passage`), and a text change with no actionable
  signal.
- Negation recognition covers only the listed phrasings (`no se modifica`,
  `sin que se modifique`, `no deja sin efecto`, `no pierde vigencia`,
  `en ningún caso`, `tampoco`, `nunca`, and their listed variants). Other negative
  wording is read as positive or missed, so a correctly negated sentence can still
  look like a change (it is then ambiguous and review-required, never
  machine-evident).
- A failed or rejected ingestion is reported as `analysis_failure:
  no_extracted_document` with no review reason and does not raise the gate on its
  own; if those are the only unresolved candidates the CLI still exits `0`, so
  exit status alone does not report a gap and the ingestion state must be checked
  separately.
- Static deadline wording (`el plazo … hasta …`, `la vigencia … hasta …`) without
  change wording is not a validity signal, so a deadline that changed only inside
  such a sentence is detected through the text diff and
  `text_changed_without_signal`, not through a validity link.
- Only versions recorded by candidate ingestion can be compared; a file replaced
  behind an unchanged URL without a new ingestion version is invisible.
- Nothing here schedules a run, publishes a review PR, or approves a change. The
  planned reviewed-update workflow and its human approval remain unimplemented.
