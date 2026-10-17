# Manijero backend

The local FastAPI service exposes `GET /health` and a source-grounded `POST /ask`:

```sh
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"question":"¿Qué información hay?","land_context":{"mode":"general","lands":[]}}'
```

Successful response:

```json
{"status":"ok","service":"manijero-backend"}
```

`/health` reports only that this process is serving HTTP requests. It does not
check corpus readiness. `/ask` reads the local `knowledge/source_catalog.json`
and `knowledge/passages.json` artifacts and uses the accepted retrieval,
grounding, abstention, and land-clarification decisions. It does not call a
hosted model or the network.

The canonical corpus is currently empty, so `/ask` safely returns the pinned
abstention with no sources. Fixture-backed answers in tests are synthetic and
do not establish legal coverage. Invalid or unreadable corpus files and
campaign-tagged sources return a generic `503`; malformed JSON returns `400`,
and valid JSON that violates the request contract returns `422`. Error responses
do not echo question, land, file, or corpus values.

## Offline retrieval baseline

`app/retrieval.py` is the offline retrieval boundary over reviewed passages of
approved catalog sources. It is standard-library only, never performs network
access, re-validates the catalog with `app/source_catalog.py`, and refuses to
index when that catalog is invalid. The `/ask` route composes it with the
accepted grounded-answer pipeline; no LLM call is configured.

Run the report-only baseline against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints per-question expected-passage ranks plus `hit@k`, `recall@k`, and MRR
(`--json` for machine-readable output). Thresholds are **not** enforced: the
numbers come from a small synthetic fixture corpus, not from real user questions
or legal documents. See `knowledge/README.md` for the passage-set contract and
the eligibility rules.

## Offline grounded answer generation

`app/generation.py` turns retrieval candidates into a plain-Spanish answer whose
material claims are each traceable to a reviewed passage. It imports `Retriever`
and `RetrievedPassage` from `app/retrieval.py`, which stay the only evidence
source: generation never re-reads the catalog or the passage set and never
re-implements eligibility.

It is standard-library only, offline, and configured with **no model provider**.
The default and only enabled generator is the code-composed extractive one; a
draft is re-checked by `verify_draft` before assembly, so a citation marker that
resolves to nothing, an uncited sentence, a figure or date absent from the cited
passage, a non-literal `critical` claim, or an eligibility assertion
(`tienes derecho a`) rejects the whole draft. The pipeline then returns a
`NotAnswered` reason code and no text; `safe_abstention` owns the user-facing
limitation and next step.

Run the report-only grounded-generation tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, the produced answer, every material claim
with its cited candidate numbers, and the per-claim grounding verdict
(`--json` for machine-readable output). Grounding invariants are **enforced**
(exit `1`); answer coverage is not, unless `--fail-on-miss` is passed. `/health`
remains liveness-only, and no model provider is configured.

## Offline abstention decisions

`app/abstention.py` turns every "no safe answer" outcome into one deterministic,
offline, code-owned abstention. It is standard-library only, imports
`app/generation.py` and `app/retrieval.py` unchanged, and never reads a catalog
or a passage file itself, never calls a model or the network, and never emits a
draft sentence, candidate excerpt, source, figure, or date.

The taxonomy is stable and machine-readable. Pre-checks (run before the
generator) and pipeline mappings produce exactly one reason:

| Reason | Trigger |
|---|---|
| `invalid_question` | Blank question, or longer than the accepted 2,000-character bound. |
| `no_evidence` | Retrieval returned no candidate (generation `no_candidates`). |
| `insufficient_evidence` | Candidates existed but no verifiable claim could be assembled (generation `grounding_failed`). |
| `stale_evidence` | The corpus declares sources but none is eligible as of `--as-of` (expired, non-`approved`, or non-`current`). |
| `conflicting_evidence` | Two `critical` candidates in the citation window state different values for the same documented unit. |
| `false_premise` | The question presupposes an instrument/article reference that no retrieved candidate contains. |
| `unsafe_request` | A generated claim asserts the person's legal status (generation `policy_failed`). |
| `generator_abstained` | The generator explicitly declined; its copy is discarded. |
| `generation_error` | The generator raised or returned an unusable object. |

Server-side copy is **code-owned**: `ABSTENTION_MESSAGES` maps every reason to one
pinned plain-Spanish message, an `Abstention` has no text field, and no message
contains a digit or a date, so an abstention can never invent a deadline or an
amount. `to_abstention_response` emits exactly the accepted `AskResponse` keys
with `status: "abstained"`, `sources: []`, and `land_ids_to_choose: []`. Because
`AskResponse` rejects extra properties, the sub-reason stays a Python-level value
and `contracts/` is untouched. Detection is lexical and conservative (a retrieval
miss or two unrelated critical passages sharing a unit can abstain); that is the
safe direction, and the measured trap set and any score threshold belong to
`land_safety_evaluation`.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_abstention.py \
  --catalog backend/tests/fixtures/abstention/catalog.json \
  --passages backend/tests/fixtures/abstention/passages.json \
  --eval backend/tests/fixtures/abstention/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, reason, generation reason, issue codes, and
emitted message (`--json` for machine-readable output), and reports whether the
corpus is `current` or `not_current`. Abstention invariants (no sources, no land
choices, a non-blank message at most 1,200 characters with no digit or date, and
a reason inside the taxonomy) are **enforced** (exit `1`); outcome coverage is not
unless `--fail-on-miss` is passed. A catalog whose sources are all ineligible as
of `--as-of` abstains as `stale_evidence` for every question; a malformed passage
set, an unknown `source_id`, or an unreadable file stays a hard error (exit `2`).
`/health` remains liveness-only, and no model provider is configured.

## Offline land clarification decisions

`app/clarification.py` makes the accepted `needs_land_clarification` response actually happen. It
composes the accepted modules unchanged (`app/retrieval.py`, `app/abstention.py`,
`app/generation.py`): it never reads a catalog or a passage file itself, never calls a model or the
network, and never filters by applicability anywhere else.

When the question depends on a detail the supplied lands differ on, the person is asked which land
(or lands) the question is about instead of the service guessing one arbitrarily. Only the opaque
local ids are returned on the wire; the client owns the names and collects the selection, so no
name, note, area, or timestamp leaves the device.

- A clarification is offered **only** for `mode: all_active` with **two or more** lands. `general`,
  a single land, and a `selected` request (the person has already chosen) delegate to the accepted
  `answer_or_abstain`, so a `selected` request is never asked to clarify again.
- The only discriminating dimensions are `water_regime` and `production_method` (the two a request
  can carry); `crop` is not a request field, so a `crop` restriction applies to every land and never
  discriminates. Detection is conservative and lexical, in the citation window (the first `max_claims`
  candidates, matching `abstention`).
- An omitted, blank, or `unknown` land attribute is compatible with every candidate and never
  excludes one; only a known value that disagrees with a candidate's declared applicability excludes
  that candidate, and no value is ever inferred.
- A clarification payload is exactly the accepted `AskResponse` keys with
  `status: "needs_land_clarification"`, `answer: ""`, `sources: []`, `land_scope: "selected"`, and a
  non-empty, unique list of the request's own land ids. `contracts/` is untouched.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_clarification.py \
  --catalog backend/tests/fixtures/clarification/catalog.json \
  --passages backend/tests/fixtures/clarification/passages.json \
  --eval backend/tests/fixtures/clarification/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's outcome, the chosen land ids for a clarification, and the per-outcome
counts (`--json` for machine-readable output). Clarification invariants (empty answer, no sources, a
non-empty list drawn from the request's own land ids) are **enforced** (exit `1`); outcome coverage is
not unless `--fail-on-miss` is passed. A malformed passage set, an unknown `source_id`, or an
unreadable file stays a hard error (exit `2`). `/health` remains liveness-only, and no model
provider is configured.

## Offline land-safety evaluation

`app/land_safety_eval.py` is the offline, report-only safety harness. It runs the
accepted end-to-end decision (`app/clarification.py::answer_with_clarification`,
which already composes retrieval, grounding, abstention, and land clarification)
over a reviewed, source-anchored case set and reports, per category, whether the
service returned the correct sources, abstained safely, or clarified the correct
land. It imports the accepted modules unchanged: it never re-implements
eligibility, grounding, or clarification, never reads a catalog or a passage file
itself, never configures a model provider, and never touches the network. Grading
is deterministic rule checking, not a semantic judge.

A case is a Git-tracked, human-reviewed artifact. A case whose expectation turns
on a critical fact must carry a completed `review` block; without it the set fails
closed at load time (exit `2`). The harness records that provenance but a human
must verify the fact itself. The case-set contract is `knowledge/land_safety_eval.schema.json`
(`land-safety-eval-v1`); see `knowledge/README.md` for the fields and the review
procedure.

Run the report-only tool against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_land_safety.py \
  --catalog backend/tests/fixtures/land_safety/catalog.json \
  --passages backend/tests/fixtures/land_safety/passages.json \
  --cases backend/tests/fixtures/land_safety/cases.json \
  --as-of 2026-10-13 --k 5
```

It prints each case's outcome and per-check verdicts, the per-category table, the
metric block, and the critical-review section (`--json` for machine-readable
output). The enforced **safety invariants** (a payload that leaks or invents:
an abstention carrying a source, a figure, or a date; a clarification carrying an
answer or a foreign land id; an answered payload with no source or an
out-of-range marker) make it exit `1`. Coverage metrics are **report-only**: an
expected-source/clarification mismatch only exits `1` with `--fail-on-miss`, and
`--passages`/`--cases` may be omitted for a corpus summary that invents nothing.
`/health` remains liveness-only, and no model provider is configured.

The measured fixture baseline is: `covered_source_hit_rate` `1.000 (2/2)`,
`correct_abstention_rate` `1.000 (2/2)`, `correct_clarification_rate`
`1.000 (1/1)`, `no_over_clarification_rate` `1.000 (3/3)`, and
`expected_outcome_match_rate` `1.000 (6/6)`. It is **synthetic and
implementer-authored**: it exercises the mechanism and the trap taxonomy, not
legal coverage or real user questions, and it is not legal-coverage evidence.
The `MasterPlanV3` §9.2 numbers (`hit@5 85%`, correct abstention `100%`, invented
numbers/dates `0`) are **inherited proposals, not enforced release gates**;
enforcement is a later, separately agreed change.

Tests:

```sh
cd backend && python -m pytest
```
