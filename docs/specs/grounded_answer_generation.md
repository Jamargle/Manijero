# Feature Spec: `grounded_answer_generation`

## Source metadata

- Feature: `grounded_answer_generation` — Generate an evidence-grounded answer
- Area: backend
- Depends on: `answer_api_contract` (accepted), `source_retrieval` (accepted)
- Feature-list behavior: for a covered question, the assistant returns a plain-Spanish answer whose material claims are supported by retrieved approved passages.
- Feature-list verification: evaluate a covered source-anchored question and check each material claim against its cited passage.
- Feature-list note: never treat the language model as the source of legal facts.
- Scope size: one internal claim/answer model plus one offline generation flow (retrieve → draft → verify → assemble); correctly sized, and it deliberately stops at the abstention boundary owned by `safe_abstention`.

## Goal

Turn a covered plain-Spanish question into an answer whose **material claims are each supported by a retrieved, reviewed passage of an approved source**. Implement this as a deterministic, offline, dependency-free pipeline in which code (not a model) selects the evidence, assigns citations, and re-checks every claim before assembly. Ship a code-composed, extractive generator as the default and only enabled path, plus a `GroundingGenerator` seam for a future hosted model that must pass the **same** verification and is discarded when it cannot. The generator boundary is designed so that a draft produced by a model can never introduce a fact: any claim without a citation, any figure or date absent from its cited passage, and any eligibility assertion is rejected, never weakened.

## Non-goals

- Serving HTTP. No `/ask` route, no FastAPI dependency on the pipeline, no client/shared changes. `backend/app/main.py` keeps `/health` as its only route. (See Risks: no feature currently owns `/ask` wiring.)
- Implementing or calling any model provider, prompt, API key, rate limit, cache, or network call. No dependency is added to `backend/requirements.txt`.
- Rewriting legal text into fresh prose. A hosted-model rephrasing path is deferred pending the provider/privacy review already recorded as an open question; when it lands it must reuse `verify_draft`.
- Abstention policy: detecting stale/conflicting/false-premise questions and producing the plain-Spanish limitation and next step. That is `safe_abstention`; this feature only returns a machine-readable not-answered reason code.
- Land-based selection and applicability filtering (`minimal_land_context`, `land_clarification`), land-scope presentation (`answer_land_scope`), and any eligibility inference.
- Chunk-level/semantic grounding (a judge/NLI that decides whether a claim is *entailed* by its passage). Only citation, figure/date, extractive-literal, coherence, and policy checks are in scope.
- Adding real legal documents, deadlines, amounts, or article numbers. All fixtures stay synthetic and labeled.
- Changing `contracts/`, the accepted `AnswerSource`/`AskResponse` schemas, `backend/app/retrieval.py`, or `backend/app/source_catalog.py`.

## Job story

When retrieval has found reviewed passages for a covered question, I want a code-controlled step that writes the answer only from those passages, attaches a citation to every material claim, and refuses to emit anything it cannot trace back to a cited passage — because a person who trusts a wrong Spanish deadline or amount can lose real money.

## Acceptance scenarios

### Covered question returns a cited, grounded answer

Given a covered source-anchored fixture question whose expected passage is retrieved from an approved, current catalog, when the pipeline runs with an explicit `--as-of` and `--k`, then it returns `status: answered` with a non-empty plain-Spanish `answer` of at most 1200 characters, at least one `AnswerSource`, `land_ids_to_choose: []`, and every material claim carrying at least one citation marker that resolves to a returned candidate.

### Every material claim is traceable to its cited passage

Given an answer claim, when it is verified, then each of its figures and dates also appears in the text of the passage(s) it cites, and a claim whose figure is absent from its cited passage is rejected rather than emitted; for a passage flagged `critical`, the claim must additionally be a literal (whitespace/case/diacritic-normalized) substring of the cited excerpt.

### The model is never the source of legal facts

Given an injected draft that cites a passage outside the candidate set, omits a citation for a sentence, declares sources that disagree with its inline markers, invents a figure, date, or article number, or asserts eligibility ("tienes derecho a…"), when the draft is verified, then it is rejected with specific issue codes, no part of it reaches the assembled response, and the pipeline returns a not-answered reason code instead.

### No evidence means no answer

Given the canonical empty catalog (or a question with no lexical match), when the pipeline runs, then it returns `no_candidates`, generates no text, and does not call any model or host, because retrieval already returns no positive-score candidates.

### Deterministic and offline

Given the same catalog, passage set, question, `--as-of`, and `k`, when the pipeline runs twice, then the output is identical, and a socket guard that blocks `socket.socket` still lets the pipeline produce the answer.

### Output conforms to the accepted contract without changing it

Given an assembled answered response, when its keys and types are compared with `contracts/openapi.yaml#/components/schemas/AskResponse`, then it matches exactly (required keys, enums, 1200-character bound, non-empty sources for `answered`), `python3 contracts/validate_examples.py` still passes, and `contracts/` is unchanged.

## Technical approach

### Evidence boundary (interface with retrieval)

`backend/app/retrieval.py` stays untouched and is the **only** evidence source. `backend/app/generation.py` imports `Retriever`, `RetrievedPassage`, `DEFAULT_K`, `RetrievalError`, `CatalogRejectedError`, and `PassageSetError` from it; it never re-reads the catalog or the passage set, never re-implements eligibility, and never falls back to unreviewed content.

- Evidence enters as `Retriever.search(question, k)` results, converted to `numbered_candidates = ((passage.rank, passage), ...)`. Marker `[n]` means "candidate number `n`", i.e. `RetrievedPassage.rank`; the mapping is positional and deterministic.
- `AnswerSource` fields come from `RetrievedPassage` unchanged (`title`, `issuing_body`, `url`, `location`, `published_or_updated_on`, `verified_on`, `excerpt`). Retrieval-local fields (`passage_id`, `source_id`, `applicability`, `critical`, `score`, `rank`) never cross into the response payload.
- An empty candidate tuple is the single "no evidence" signal (retrieval never returns a zero-score candidate).

### Answer-generation policy

1. **The model is a writer, never an authority.** Every material claim must carry at least one citation marker that resolves to a retrieved candidate. Code selects the candidate set, normalizes markers, and re-checks the draft; anything not traceable is discarded.
2. **Fail closed.** A rejected draft is never partially emitted, never repaired by dropping only the bad sentence (the whole draft is rejected), and never replaced by model knowledge or by an unreviewed passage. The pipeline then returns a not-answered reason code.
3. **Citations are code-owned.** A citation marker is `[n]` for candidate `n`, and the response `sources` array contains exactly the cited candidates, deduplicated and in ascending candidate order, so marker `[n]` always means `sources[n-1]`.
4. **Figures and dates are checked, not promised.** Every figure or date in a claim must also occur in the text of the passage(s) that claim cites. No other figure-producing path exists: the pipeline adds no dates of its own, so every date a user sees is traceable to a reviewed passage. (The per-source `verified_on` field carries the "last verified" information.)
5. **Critical evidence is extractive.** For a passage whose `critical` flag is true (deadlines, amounts, thresholds, requirements), the claim must be a literal substring of the cited excerpt after whitespace/case/diacritic normalization, so a critical figure is copied, never paraphrased.
6. **No eligibility, no personalized legal advice.** A claim that asserts the person's legal status is rejected by a small, tested Spanish phrase check. Land attributes never produce a legal conclusion.
7. **Plain Spanish and a code-added notice.** User-facing text is short-sentence Spanish; the orientative notice is added by code, not produced by a generator.
8. **Question and passage text are untrusted data.** Instructions inside the question or an excerpt cannot change these rules; no rule depends on prompt compliance. The verifier is the authority, and no model is called when there are no candidates.
9. **Abstention boundary.** This feature guarantees "no unsupported material claim is ever emitted" and returns reason codes; `safe_abstention` owns deciding that no safe answer exists, the plain-Spanish limitation, the next step, and the `abstained` response assembly.

### Internal model and pipeline

`backend/app/generation.py` (standard library only: `dataclasses`, `datetime`, `re`, `unicodedata`, `typing`, plus `app.retrieval`):

- `DraftAnswer(status: str, answer: str, source_markers: tuple[int, ...])` — the generator-facing shape mirroring `MasterPlanV3` §8.1 (`status`, `answer`, `sources`), so a model JSON can be adapted without redesign.
- `GroundingIssue(code: str, detail: str)` and `GroundingReport(ok, issues, claims)`; issue codes at least: `incoherent_draft`, `empty_answer`, `no_markers`, `unknown_marker`, `marker_mismatch`, `uncited_sentence`, `figure_unsupported`, `critical_not_literal`, `eligibility_claim`, `answer_too_long`. Diagnostics name codes, candidate numbers, and rule names only — never the question text or an excerpt (privacy, and consistent with the catalog/retrieval modules).
- `GroundingGenerator` protocol: `generate(question, numbered_candidates, *, as_of) -> DraftAnswer`.
- `ExtractiveGroundingGenerator(max_claims=2)` — the default: for the top `max_claims` candidates in rank order, one claim per candidate whose text is the candidate's `excerpt` followed by its marker. Deterministic, offline, no clock, no model.
- `verify_draft(draft, numbered_candidates) -> GroundingReport` — the checks in the next section.
- `generate_grounded_answer(question, retriever, *, k=DEFAULT_K, max_claims=2, land_scope="general", as_of, generator=None)` returning either `Answered(answer, claims, sources, ...)` or `NotAnswered(reason, issues)`, with reasons `invalid_question`, `no_candidates`, `generator_abstained`, `grounding_failed`, `policy_failed`, `generation_error`.
- `to_answer_response(answered) -> dict` — assembles the accepted `AskResponse` payload; rejects a `land_scope` outside `general`/`all_active`/`selected`.

Blank questions and questions longer than the contract's 2000 characters return `invalid_question` without retrieving or generating.

### Draft verification rules (the grounding gate)

Applied to every draft, whatever produced it:

1. **Schema/coherence:** `status` is `answered` and `answer` is non-blank; otherwise `incoherent_draft`/`empty_answer`. A generator-reported `abstained` becomes `generator_abstained` (its copy is discarded; `safe_abstention` owns that text).
2. **Markers:** the inline `[n]` markers found in `answer` are non-empty, every `n` is an existing candidate rank, and the declared `source_markers` set equals the inline marker set; otherwise `no_markers`, `unknown_marker`, or `marker_mismatch`.
3. **Per-sentence citation:** code splits `answer` into sentences and requires each sentence to carry at least one marker; otherwise `uncited_sentence`. Markers are stripped from the sentence text before steps 4–5.
4. **Figure/date grounding:** figures and dates extracted from a sentence must be a subset of those extracted from the union of its cited passages' excerpts (normalized dates, decimal comma/point, thousands separators, `%`); otherwise `figure_unsupported`.
5. **Critical extractive mode:** if any cited passage has `critical: true`, the sentence must be a literal substring of that excerpt after normalization; otherwise `critical_not_literal`.
6. **Eligibility policy:** a small tested Spanish phrase list (starter set: `tienes derecho a`, `tiene derecho a`, `puedes cobrar`, `puede cobrar`, `cumples los requisitos`, `cumple los requisitos`, `vas a recibir`, `te corresponde cobrar`) triggers `eligibility_claim`.
7. **Length:** the notice plus one claim must fit 1200 characters; otherwise `answer_too_long`.

Assembly then: prepends the code-added lead-in, joins the surviving verified claims with their markers, appends the code-added notice, drops trailing claims (never mid-sentence) until the payload fits 1200 characters, keeps at least one claim or returns `NotAnswered`, and emits `sources` as contract-shaped `AnswerSource` dicts (exactly the seven contract keys) deduplicated in ascending cited order.

Pinned user-facing strings (byte-for-byte tested; plain Spanish, no jargon):

- Lead-in: `Según los documentos oficiales revisados:`
- Notice: `Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional.`

Neither contains a digit or a date, so the "every date the user sees is grounded" rule holds by construction.

### Evaluation harness

`backend/scripts/evaluate_generation.py`, an offline report-only CLI mirroring `evaluate_retrieval.py` (explicit `--as-of`/`--k`, `--json` with `sort_keys=True`/`ensure_ascii=False`, no network, diagnostics without content):

```
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

The eval file is JSONL with exactly `{"question", "expected_passage_ids", "expect"}` where `expect` is `answered` or `no_candidates`. The loader rejects unknown keys, a blank question, an empty `expected_passage_ids`, and — addressing accepted retrieval finding F4 — an `expected_passage_ids` value that is not present in the built index.

Per question it prints the outcome, the produced answer, each material claim with its cited candidate numbers, and the per-claim grounding verdict; then aggregates answers produced, claims checked, ungrounded claims, invented sources, and no-evidence outcomes. Exit codes: `0` report produced with every grounding invariant holding; `1` a grounding invariant failed (ungrounded claim, unknown/undeclared marker, eligibility claim, non-literal critical claim) or an `expect: answered` question produced no answer only when `--fail-on-miss` is passed; `2` unreadable/rejected input or invalid arguments.

### Error and failure behavior

- **Rejected catalog or passage set:** the exception propagates from `Retriever.from_documents`; the pipeline never indexes partial data, and the CLI exits `2` with the located diagnostics. Generation never catches and continues.
- **No candidates:** `NotAnswered("no_candidates")`, no text, no model call.
- **Unverifiable draft:** `NotAnswered("grounding_failed" | "policy_failed")` carrying the issue codes; nothing from the draft is emitted. In the CLI this is a hard exit `1`, because it means a generator produced ungrounded output.
- **Generator error (future model path):** `NotAnswered("generation_error")`; no fallback to model knowledge, no partial answer. Client-facing retry/offline copy is `network_error_recovery`.
- **Invalid question:** `NotAnswered("invalid_question")` for blank or over-2000-character questions.
- **No content logging:** no raw question, land context, or excerpt text in diagnostics, exceptions, or CLI output beyond the answer the tool explicitly reports for review; a test asserts the rejection messages contain no excerpt text.
- **No network:** reading and generation are local-only; a socket-guard test must still allow the pipeline to run.

## Expected file changes

- Create `backend/app/generation.py` — draft model, grounding verifier, extractive generator, pipeline, response assembly.
- Create `backend/scripts/evaluate_generation.py` — offline evaluation CLI.
- Create `backend/tests/test_generation.py` — focused tests.
- Create `backend/tests/fixtures/generation/` — synthetic catalog, passage set (including a labeled fictitious-figure `critical` passage so figure and extractive checks are exercised), `eval_questions.jsonl`, and `drafts_ungrounded.json` (recorded fake-generator drafts that must be rejected, one per issue code).
- Update `knowledge/README.md` — a short "Grounded answer generation" section: the pipeline reads only retrieval output, the citation/figure/extractive rules, the evaluation command, and reviewer guidance that passage `text` is quoted to users, so excerpts should stay short and understandable.
- Update `backend/README.md` — the offline generation module and CLI; `/health` remains the only route and no model provider is configured.
- Update `feature_list.json` and `PROGRESS.md` after implementation/validation with actual status, commands, and results (the orchestrator owns this; the planning pass records the spec link only).

`scripts/init.sh`: no change. It already executes the KMP verification checks for the current repo state; this backend slice is verified with the documented Python commands, and no long-running process is added to the wrapper. No changes to `contracts/`, `backend/app/retrieval.py`, `backend/app/source_catalog.py`, `backend/app/main.py`, `knowledge/source_catalog.json`, `knowledge/passages.schema.json`, `backend/requirements.txt`, or any client/shared code. No canonical `knowledge/passages.json` is created.

## Visual design impact

None. No Compose UI and no client code change. The generated `answer` carries one code-added Spanish notice; how it is displayed (and whether the notice is later moved to the client) belongs to `response_states` / `answer_source_cards`.

## Durable documentation impact

- `knowledge/README.md`: update; it is the durable operational contract for the corpus and now also documents how reviewed passages become user-visible answers.
- `backend/README.md`: update; it documents the backend boundaries, including that generation is offline and no provider is configured.
- `AGENTS.md`: no update; "do not invent legal facts, ground regulatory claims in approved official sources, cite them, and abstain when evidence is inadequate" already governs this work, and `backend/app/generation.py` makes it executable.
- `CONTEXT.md`, `docs/build-brief.md`, `docs/domain-model.md`, `DESIGN.md`, `MasterPlanV3.md`: no update; the response principles, source definition, and plan sections already state these rules.
- `ARCHITECTURE.md`: not needed; absent, and a focused offline pipeline does not establish a broader runtime architecture.
- `CONSTRAINTS.md`: not needed for this slice (AGENTS.md already states the rule and the verifier enforces it). Create it with a single MUST line only if implementation reveals a mechanism-level rule later features must follow and no existing doc covers (for example, "no component may emit a user-visible answer that bypasses `verify_draft`").
- `PROGRESS.md` and `feature_list.json`: update after verification with the real command output; state plainly that fixtures are synthetic, no model provider is configured, the generator is extractive, and metrics are not release gates.

## Risks and handoff notes

The extractive default cannot write fresh prose, so answer readability and plain-Spanish quality are bounded by the reviewed excerpts and by retrieval quality; a hosted-model rephrasing path is deferred pending the provider/privacy review and must pass `verify_draft` unchanged. The checks are lexical: figure presence is not entailment (a passage can contain a number that a claim misreads), the eligibility check is a phrase list, and semantic grounding/conflict detection are explicitly deferred to `safe_abstention` and a later judge. Retrieval thresholds remain uncalibrated, so "covered" here means "retrieval returned at least one candidate and a claim verified", not a measured adequacy gate.

Handoffs: `safe_abstention` consumes the `NotAnswered` reason codes and owns the abstention copy, next step, and stale/conflict/false-premise detection; `land_clarification`/`minimal_land_context` own `land_scope` and applicability; `answer_source_cards`/`response_states` own how markers `[n]`, the notice, and verification dates are presented (and must not duplicate the notice); `land_safety_evaluation` owns measurement. No feature in `feature_list.json` currently owns wiring `POST /ask` in FastAPI or the client's production `AnswerService`, so a live end-to-end answer remains a separate slice — recommend it after `safe_abstention`, when one route can serve all three accepted statuses. Non-blocking observation for the orchestrator: `scripts/init.sh`'s `--check` text still lists retrieval and the visual foundation as deferred.

### Implementation findings

Recorded while implementing the spec; none changes the goal or the design.

- The extractive default requires each reviewed excerpt to be **one sentence**.
  The per-sentence citation rule splits the draft on sentence boundaries, so a
  multi-sentence excerpt whose single trailing marker lands after the final
  period leaves the earlier sentences uncited and the whole draft fails closed
  (`uncited_sentence`). Excerpts should stay single-sentence (see
  `knowledge/README.md`).
- A reviewed excerpt that contains a starter eligibility phrase (for example
  `tienes derecho a`) is unanswerable through the extractive default, because
  the verbatim claim is rejected by the policy check. This is fail closed and
  intentional; the reviewer guidance says to avoid such phrasing in an excerpt.
- `NotAnswered` additionally carries the per-claim verdicts (`claims`) when a
  draft was verified and rejected, so the evaluation CLI can report exactly
  which claim failed. Nothing from a rejected draft is ever emitted as an
  answer.
- The evaluation loader's index check applies to every line, so a line cannot
  reference an id the built index does not contain; with the canonical empty
  catalog and no passages, supply no `--eval` (the index has nothing to grade
  against). This is the strongest reading of the F4-driven requirement.


## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 backend/scripts/evaluate_generation.py --catalog backend/tests/fixtures/generation/catalog.json --passages backend/tests/fixtures/generation/passages.json --eval backend/tests/fixtures/generation/eval_questions.jsonl --as-of 2026-10-13 --k 5
./scripts/init.sh --backend-tests tests/test_generation.py
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/specs/grounded_answer_generation.appendix.md`](grounded_answer_generation.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/grounded_answer_generation.md` remains the authoritative acceptance record.
