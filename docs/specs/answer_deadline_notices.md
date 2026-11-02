# Add code-owned deadline notices: cooperative internal deadlines and already-expired deadlines

## Source metadata

- `id`: answer_deadline_notices · `area`: backend · `depends_on`: backend_campaign_validity,
  backend_citation_hardening (both accepted) · `status` at planning: not_started
- User-visible behavior: a grounded answer that cites a passage with a reviewed official deadline
  ends with one extra paragraph of fixed Spanish sentences. One says the cooperative or entidad
  colaboradora may set an earlier date. When the deadline has passed, another states the exact
  date it ended. No other answer changes.
- Verification: fixture and real-corpus tests, the report-only 14-case evaluation, and the full
  backend suite; no Ollama, network, device, or owner step.
- Notes — **Owner decisions 2026-11-03**:
  1. Notices are fixed Spanish sentences owned by code, never written by the model, of two
     kinds: (a) a cooperative/entidad colaboradora may set an earlier internal deadline, so check
     with them first; (b) the official deadline has already passed, stating the exact end date.
  2. Deadline dates come from reviewed structured metadata added to the official sources in the
     knowledge catalog/passages, never parsed from free text; with no reviewed date, no expired
     notice.
  3. Expiry is judged against the injected UTC as-of date used by campaign validity
     ([`backend_campaign_validity`](backend_campaign_validity.md)).
  4. The notice is appended as its own final paragraph of the answer text: no app change and
     no contract change.
  5. The cooperative notice shows whenever a grounded answer cites a source with an official
     deadline.
  6. Acceptance: validator accept is final; no owner walkthrough.
- Planner choice within decision 2: the metadata is a **passage** key (`official_deadline`),
  because one passage states the deadline. A source-level key would also tag passages of the
  same document that state none.

## Goal

Warn a grower, in code-owned Spanish, about two traps that a cited official date does not show
on its own. The intermediary may have an earlier internal date. The deadline may already have
passed, even though its campaign source is still valid.

## Non-goals

- No change to `contracts/`, `shared/`, the app, response or source fields, abstention copy,
  `LEAD_IN`, `NOTICE`, `verify_draft`, `extract_numeric_facts`, `extract_figures`, campaign
  selection, validity filtering, or retrieval ranking.
- No runtime date parsing from text, model-written notice, source-level deadline key, start
  dates, ranges, per-land or per-cooperative dates, or reminders.
- No new dependency, owner command, or `scripts/init.sh` change
  ([`operations.md`](../constraints/operations.md) does not apply).

## Job story

When an answer quotes an official deadline, I want to be told plainly whether it has passed, and
to check my cooperative's own date first. That way I don't miss an earlier internal cut-off, and
I don't act on a window that has already closed.

## Acceptance Scenarios

The answer text equals today's assembled answer + `"\n\n"` + the paragraph. Exact sentences:
`EXPIRED` = `El plazo oficial terminó el D de <mes> de YYYY.` (no leading zero, lowercase
month) and `COOPERATIVE` = `Tu cooperativa o entidad colaboradora puede tener una fecha
anterior al plazo oficial: pregúntale primero.` The paragraph is the `EXPIRED` sentences
(distinct dates, ascending), then `COOPERATIVE` once, joined by single spaces.

### 1. An open cited deadline adds only the cooperative notice

Given a cited passage with `official_deadline` `2031-05-15` · When `as_of` is `2031-05-15` (the
last day is still open) or earlier, or `as_of` is `None` · Then the paragraph is `COOPERATIVE`.

### 2. A passed deadline adds its exact end date

Given the same passage · When `as_of` is `2031-05-16` · Then the paragraph is `El plazo oficial
terminó el 15 de mayo de 2031. ` + `COOPERATIVE`.

### 3. Several cited deadlines produce one ordered paragraph

Given cited passed deadlines `2031-06-15` and `2031-05-15` · Then the 15 May sentence, then
the 15 June sentence, then one `COOPERATIVE`. The same date twice gives one `EXPIRED`. When one
deadline has passed and one is still open, only the passed date gets an `EXPIRED` sentence.

### 4. No reviewed date or no citation, no notice

Given a cited passage whose text says "hasta el 15 de mayo de 2031" but has no
`official_deadline`, and a later `as_of` · Then the answer is byte-identical to today's. A
passage with `official_deadline` that is retrieved but not cited (beyond `max_claims` or dropped
to fit) adds nothing.

### 5. Abstentions and clarifications never carry a notice

Given any abstention (rejected draft, stale corpus, question-year guard, no evidence) or a
`needs_land_clarification` result · Then the payload is exactly today's pinned response.

### 6. Notices skip the numeric check and cannot come from a model

Given a passage stating "finalizará el 15 de junio" (no year) with a passed `official_deadline`
`2031-06-15` · Then the answer is `answered` and includes `El plazo oficial terminó el 15 de
junio de 2031.`, because `verify_draft` runs on the draft before the paragraph is added. Given
a Gemini or local draft containing `COOPERATIVE` or the `El plazo oficial terminó el` prefix
(any case or accents) · Then `parse_draft` raises `output_code_owned_text`, and the extractive
fallback answer carries the paragraph exactly once.

### 7. The paragraph always fits the 1200-character answer

Given claims whose assembly plus paragraph exceeds 1200 characters · Then trailing claims are
dropped whole, and the paragraph is recomputed from the claims that remain. Given the first
claim plus its paragraph cannot fit · Then the existing `answer_too_long` path abstains
(`insufficient_evidence`): a deadline answer is never shown without its notice. Every real
passage with `official_deadline` fits alone with its worst-case paragraph.

### 8. The metadata is validated and the real corpus carries it

Given an `official_deadline` that is not a real `YYYY-MM-DD` date (for example `2026-02-30`,
`15/05/2026`, `null`, or `20260515`) · Then `validate_passage_set` reports it, and `/ask`
returns the generic 503. The schema lists the key, and the schema-sync test passes. In
`knowledge/passages.json`, `pasaje-plazo-presentacion-2026-andalucia` has `2026-05-15`,
`pasaje-plazo-modificacion-2026-andalucia` has `2026-06-15`, and no other passage has the key.
Each value's day and month appear in its excerpt (`extract_numeric_facts`), and its year equals
the source's `campaign`.

### 9. The API and evaluations are otherwise unchanged

Answered responses keep today's five keys and seven `AnswerSource` keys, and expose no deadline
field; `contracts/validate_examples.py` passes. In the 14-case evaluation at `--as-of
2026-10-31`, the state, source, and passage aggregates equal the pre-change baseline. Any
difference is listed per case in evidence, and must come only from claim fitting (scenario 7).

## Technical approach

- New `backend/app/deadline_notices.py` (stdlib only, no clock): the two pinned sentences, a
  Spanish month table, `format_spanish_date`, and `deadline_paragraph(passages, as_of) -> str`
  (empty when no passage has a deadline). It also defines `CODE_OWNED_MARKERS`, the normalized
  `COOPERATIVE` and `EXPIRED` prefix.
- `retrieval.py`: `official_deadline` joins `PASSAGE_OPTIONAL_KEYS` and is validated as a real
  ISO date. It is carried as `official_deadline: Optional[str] = None`, the last field of
  `_PassageRecord` and `RetrievedPassage`. It stays retrieval-local; `answer_source` is
  unchanged.
- `generation.py`: `generate_grounded_answer` passes the rank→passage map and `as_of` into
  `_fit_claims`. That function appends `"\n\n" + paragraph` when the paragraph is non-empty, and
  bounds the full text at 1200. Markers are renumbered as today, and the paragraph has no `[n]`.
  Extend the docstring's code-owned-notice rule.
- `gemini_generation.py`: `parse_draft` also rejects `CODE_OWNED_MARKERS`; the local provider
  reuses it.

## Expected file changes

- `backend/app/deadline_notices.py` (new); `backend/app/retrieval.py`, `generation.py`, and
  `gemini_generation.py` (modify); `knowledge/passages.json` and `passages.schema.json` (modify).
- `backend/tests/test_deadline_notices.py` (new). Modify `test_generation.py`,
  `test_retrieval.py`, `test_pac_corpus.py`, `test_gemini_generation.py`,
  `test_local_generation.py`, and `test_ask_endpoint.py`.
- The docs below. **Do not change** anything listed in Non-goals.

## Visual design impact

UI involved: no. The copy follows [`DESIGN.md`](../../DESIGN.md) "Design intent": everyday
Spanish, `tú`, a concrete next step, and no definitive legal tone. The app renders answer text
verbatim, so `"\n\n"` shows as a paragraph break.

## Durable documentation impact (required)

- `docs/constraints/answers-and-knowledge.md`: update "Answer grounding" with one MUST. Deadline
  notices are fixed code-owned sentences appended after `verify_draft`. They are driven only by a
  cited passage's reviewed `official_deadline` and the injected UTC `as_of`. They never appear on
  abstentions or clarifications, and they always fit the 1200 bound. Reason: this feature.
- `knowledge/README.md`: add an `official_deadline` row to the passage field table, plus one
  reviewer step: enter the inclusive last day, and leave the key absent when unsure.
- `backend/README.md`: one sentence in the generation paragraph.
- `docs/progress/known-limitations.md`: one line at acceptance. Only two hand-entered dates exist.
  A release or embedding index built earlier serves answers without notices until it is rebuilt.
- `ARCHITECTURE.md`, `docs/risks-and-open-questions.md`, `AGENTS.md`, `CONTEXT.md`, and
  `DESIGN.md`: not needed, because no boundary, risk entry, or UI rule changes.

## Focused verification (required)

This needs the backend environment (`./scripts/init.sh --setup-python`). Line 1 checks that the
contract examples are unchanged. Line 2 runs the touched suites. Line 3 is the report-only
evaluation: it exits `0`, and its aggregates are compared with the appendix baseline. Line 4
runs the full backend suite, because `passages.json` and answer assembly feed every answer path.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./scripts/init.sh --backend-tests tests/test_deadline_notices.py tests/test_generation.py tests/test_retrieval.py tests/test_pac_corpus.py tests/test_gemini_generation.py tests/test_local_generation.py tests/test_ask_endpoint.py
"${MANIJERO_PYTHON:-backend/.venv/bin/python}" backend/scripts/evaluate_pac_answers.py --catalog knowledge/source_catalog.json --passages knowledge/passages.json --cases knowledge/pac_answer_eval.json --active-campaign 2026 --as-of 2026-10-31 --k 5
./scripts/init.sh --backend-tests
```
<!-- verify:end -->

## Appendix

See [`answer_deadline_notices.appendix.md`](answer_deadline_notices.appendix.md) for research,
plan, evidence, and the validator checklist.
