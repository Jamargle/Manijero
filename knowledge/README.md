# Knowledge: approved sources and reviewed passages

This directory holds the admission gate for the Manijero MVP knowledge corpus.
A document may only become eligible for ingestion when a human has approved it
and its catalog metadata is complete, and only reviewed passages of such a
document are ever searchable. Both artifacts are Git-tracked text files, so
every addition and change is reviewable, diffable, and revertible.

## What this does and does not do

The catalog and its validator check **catalog policy and metadata**: identity,
provenance domain, integrity digest, dates, human review, and lifecycle state.

They do **not** prove that a document is authentic, currently in force, or
legally applicable. They never fetch a URL, follow a redirect, or inspect the
document body, and they make no legal conclusion. A validated entry means "this
metadata is complete and traceable", not "this rule is the law today".

The separate `backend/app/source_monitor.py` tool polls only explicitly
configured endpoints on approved exact hosts and records feed response
hashes/validators as operational state. It does not fetch feed-linked documents
or edit this directory's canonical artifacts. A detected change is only a
candidate for subsequent human review, not approved legal knowledge.

Retrieval over passages is **lexical and offline** as well. It ranks reviewed
excerpts by word overlap (BM25) and never downloads, parses, or chunks a
document, never reaches a model or the network, and never invents a passage.
`hit@k`/`recall@k`/MRR numbers measured on synthetic fixtures are a starting
measurement, not evidence about legal coverage or real user questions.

## Files

| File | Purpose |
|---|---|
| `source_catalog.json` | The canonical, Git-tracked catalog. Contains four reviewed official sources for the bounded 2026 PAC slice. |
| `passages.json` | The canonical, Git-tracked passage set. Contains four approved literal passages; see `pac_coverage.md` for its boundary. |
| `source_catalog.schema.json` | The readable versioned field contract (`source-catalog-v1`). |
| `passages.schema.json` | The readable versioned passage contract (`passage-set-v1`). |
| `land_safety_eval.schema.json` | The readable versioned safety-evaluation case contract (`land-safety-eval-v1`). |
| `pac_answer_eval.schema.json` | The readable versioned reviewed PAC answer-evaluation case contract (`pac-answer-eval-v1`). |
| `../backend/app/source_catalog.py` | The executable catalog validator. Must stay in sync with the schema. |
| `../backend/app/retrieval.py` | The executable passage-set validator and offline BM25 retriever. |
| `../backend/app/generation.py` | The executable grounding verifier, extractive generator, and answer assembler. |
| `../backend/app/land_safety_eval.py` | The executable safety-evaluation case-set validator and offline harness. |
| `../backend/app/answer_eval.py` | The executable PAC answer-evaluation validator and report calculation. |
| `../backend/scripts/validate_source_catalog.py` | The offline catalog command-line wrapper. |
| `../backend/scripts/evaluate_retrieval.py` | The offline retrieval baseline command-line wrapper. |
| `../backend/scripts/evaluate_generation.py` | The offline grounded-generation report command-line wrapper. |
| `../backend/scripts/evaluate_land_safety.py` | The offline land-safety report command-line wrapper. |

`source_catalog.json` contains the four independently reviewed official sources
for the bounded Andalusia PAC 2026 slice. It does not mean the corpus is broad
or supports questions outside the published coverage.

`passages.json` contains four manually curated literal passages approved by
Diego. There is no automatic ingestion or chunking pipeline; the passage format
is also exercised by synthetic fixtures under `backend/tests/fixtures/`. The
canonical passages support only the questions listed in `pac_coverage.md`.

## Andalusia PAC 2026 reviewed slice

`pac_coverage.md` records the three independently reviewed procedural topics,
approved source and passage references, and explicit gaps. Diego verified the
downloaded official copies and approved the literal passages and coverage on
2026-10-17. This bounded slice does not establish individual eligibility or aid
amounts. Do not answer outside its published coverage; the ordinary safe
abstention behavior applies to uncovered questions. Research and chronology are
documented in `docs/specs/backend_pac_corpus.appendix.md`.

`pac_answer_eval.json` is a separate, reviewed sample of end-to-end `/ask`
questions for that bounded slice. It reports state, citation/passage matching,
literal critical-fact checks, and clarification outcomes. Its case coverage and
all metrics are report-only: they are not a legal correctness certificate,
quality guarantee, or evidence about questions outside the listed cases. The
CLI receives explicit catalog and passage files, and citation matching uses
those same supplied artifacts.

## Approved issuers and hosts

Host matching is **exact**, including the `www.` alias of each domain. Lookalike
suffixes (`boe.es.example.com`), subdomains (`datos.boe.es` is not listed),
non-HTTPS URLs, URLs with embedded credentials, and site roots are rejected.

| `issuing_body` | Approved hosts |
|---|---|
| `BOE` | `boe.es`, `www.boe.es` |
| `Junta de Andalucía` | `juntadeandalucia.es`, `www.juntadeandalucia.es` |
| `FEGA` | `fega.gob.es`, `www.fega.gob.es`; plus the BOE hosts for state texts published in the BOE |
| `MAPA` | `mapa.gob.es`, `www.mapa.gob.es`; plus the BOE hosts for state texts published in the BOE |

State legislation is published in the BOE even when the issuing ministry is
MAPA or FEGA, so those issuers may use a `boe.es` URL. Registering a document
under an issuer whose hosts do not include the URL host is rejected.

Adding a new issuer or domain, or accepting a new `lifecycle_status`, is a
reviewed change to the schema, the host map, and the test suite. Never do it as
a shortcut to make a fixture pass.

## Adding a document (reviewer procedure)

1. Confirm the document is an official publication from one of the approved
   issuers and note the **original** publication URL (not a search page, not a
   consolidated convenience URL).
2. Download the original text yourself and record the download date. The
   validator does not download anything for you.
3. Compute the digest of the downloaded original:
   `shasum -a 256 <file>` and keep the lowercase value.
4. Add one entry to `sources` in `source_catalog.json` with every required
   field:

   | Field | Rule |
   |---|---|
   | `id` | Unique, stable lowercase slug, for example `rd_1048_2022`. Never reuse it. |
   | `title` | Non-blank title as published. |
   | `issuing_body` | One of the approved issuers above. |
   | `original_url` | HTTPS link to the specific published document on an approved host. |
   | `consolidated_url` | Optional; HTTPS, same issuer, and never a replacement for `original_url`. |
   | `published_on` | `YYYY-MM-DD`, on or before `downloaded_on`. |
   | `downloaded_on` | `YYYY-MM-DD`, on or before `verified_on`. |
   | `verified_on` | `YYYY-MM-DD` when a human checked the copy against the original. |
   | `content_sha256` | Lowercase 64-character SHA-256 hex digest of the downloaded original. |
   | `review_status` | Must be `approved`. |
   | `reviewed_by` | Non-blank role or identifier of the human reviewer. |
   | `reviewed_on` | `YYYY-MM-DD`, on or after `downloaded_on`. |
   | `lifecycle_status` | Must be `current`. |
   | `valid_until` | Optional `YYYY-MM-DD` for calls, deadlines, or extensions; must be on or after the validation date. |
   | `campaign` | Optional four-digit campaign year. Campaign-tagged entries require `valid_until`; expired entries and linked passages must be removed from active artifacts during reviewed campaign rotation. |
   | `critical` | Optional boolean for deadlines, amounts, and thresholds. |
   | `applicability` | Optional; record only known values. Unknown values stay absent; never write `"unknown"`. |

5. Run the validator (see below) and make sure it exits `0`.
6. Open a pull request. A named human reviewer other than the author approves
   the addition before it is merged. Any change to an approved document's
   provenance or validity is re-reviewed the same way.

No entry may be added by an automated discovery process without that human
review step.

## Running the validator

From the repository root:

```sh
python3 backend/scripts/validate_source_catalog.py knowledge/source_catalog.json --as-of 2026-10-12
```

`--as-of` is the validation date used for expiry checks. Supply it explicitly so
runs are reproducible; when it is omitted the current UTC date is used.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Catalog accepted. Reports the schema version and how many sources were checked. |
| `1` | Catalog rejected. Prints one diagnostic per violation, naming the JSON path and the violated rule. |
| `2` | The file could not be read or is not valid JSON. |

Diagnostics name the entry path (`$.sources[0].original_url`) and the rule, and
deliberately never print catalog field values or document text.

The tests live in `backend/tests/test_source_catalog.py` with synthetic fixtures
under `backend/tests/fixtures/source_catalog/`. Those fixtures are metadata test
data only; they are not a review of any real document.

## Reviewed passage sets (`passage-set-v1`)

A **passage** is one reviewed excerpt of an approved catalog document. The
readable contract is `passages.schema.json`; the executable validator is
`backend/app/retrieval.py` (`validate_passage_set`). Both must stay in sync.

```json
{
  "schema_version": "passage-set-v1",
  "passages": [
    {
      "id": "fixture-rd1048-art1-p1",
      "source_id": "rd_1048_2022",
      "location": "Art. 1",
      "text": "Fragmento sintético de prueba; no afirma ningún plazo real.",
      "critical": false,
      "applicability": { "crop": "olivar", "water_regime": "dryland" }
    }
  ]
}
```

| Field | Rule |
|---|---|
| `schema_version` | Must be `passage-set-v1`. |
| `passages` | Array of passage objects; may be empty. |
| `id` | Unique, stable lowercase slug. Never derive it from the excerpt and never reuse it. |
| `source_id` | Must resolve to an existing `id` in the approved catalog. An unknown value is a load error, never a silent skip. |
| `location` | Non-blank article, annex, page, or section inside the document. |
| `text` | The non-blank reviewed excerpt. Retrieval indexes this text only. |
| `critical` | Optional boolean for deadlines, amounts, and thresholds. When absent the source-level flag applies. |
| `applicability` | Optional; record only known values, in the same shape as the catalog. When absent the source-level applicability applies. |

Unknown keys, duplicate ids, blank text, and out-of-range applicability values
are rejected. A passage set is a Git-tracked, human-reviewed artifact: nothing
here discovers, downloads, or chunks documents for you.

### Eligibility coupling

Retrieval is a consumer of the catalog gate, not a bypass around it:

- `Retriever.from_documents` re-runs `validate_catalog` and **refuses to build an
  index** when the catalog is invalid, so a non-`approved`, non-`current`, or
  expired catalog yields no candidates and no partial index instead of
  unreviewed content.
- A passage is indexed only when its `source_id` resolves to a source that is
  `approved`, `current`, and not expired as of the supplied `--as-of` date.
- Candidates carry `title`, `issuing_body`, `url`, `location`,
  `published_or_updated_on`, `verified_on`, and `excerpt` using the accepted
  `AnswerSource` field names, plus `passage_id`, `source_id`, `applicability`,
  `critical`, `score`, and `rank`. Applicability is surfaced, never used to
  filter here; land-based selection belongs to `minimal_land_context` and
  `land_clarification`.

## Running the retrieval baseline

The baseline runs against synthetic fixtures, not the canonical PAC corpus:

```sh
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints each question's expected-passage rank and the aggregate `hit@k`,
`recall@k`, and MRR. `--json` emits the same report as JSON, and `--fail-on-miss`
opts into a non-zero exit on a miss (off by default: thresholds are **not**
release gates). `--passages` and `--eval` are optional; with an empty catalog
and no passages, the command reports zero candidates.

Exit codes: `0` report produced, `1` only with `--fail-on-miss` and a miss,
`2` an input file was unreadable or invalid. No command here performs network
access.

## Grounded answer generation

`backend/app/generation.py` turns retrieval candidates into a plain-Spanish
answer whose material claims are each traceable to a reviewed passage. It is
standard-library only, offline, and configured with **no model provider**: the
default and only enabled generator is the code-composed extractive one, which
copies reviewed excerpts verbatim. A hosted-model rephrasing path is deferred
and must pass the same verification unchanged.

What the pipeline guarantees:

- **Retrieval output is the only evidence.** Generation never re-reads the
  catalog or passage set, never re-implements eligibility, and never calls a
  model or the network when there are no candidates.
- **Citations are code-owned.** Draft markers are verified against original
  retrieval candidate ranks. After verified claims are selected, emitted answer
  markers are renumbered densely in ascending candidate-rank order; the response
  `sources` array contains exactly those cited candidates once each in that same
  order, so emitted `[n]` always means `sources[n-1]` (it need not equal the
  candidate's retrieval rank).
- **Figures and dates are checked, not promised.** Every figure or date in a
  claim must also appear in the text of the passage(s) that claim cites;
  otherwise the whole draft is rejected. The pipeline adds no date or amount of
  its own, so every figure a user sees comes from a reviewed excerpt.
- **Critical evidence is extractive.** For a passage flagged `critical`
  (deadlines, amounts, thresholds), the claim must be a literal substring of the
  cited excerpt after whitespace/case/diacritic normalization, so a critical
  figure is copied, never paraphrased.
- **No eligibility, no personalized legal advice.** A claim asserting the
  person's legal status (starter phrase list, such as `tienes derecho a`) is
  rejected. Land attributes never produce a legal conclusion.
- **Fail closed.** A rejected draft is discarded whole: never partially
  emitted, never repaired, never replaced by model knowledge or unreviewed
  content. The pipeline returns a machine-readable reason code
  (`invalid_question`, `no_candidates`, `generator_abstained`,
  `grounding_failed`, `policy_failed`, `generation_error`) and
  `safe_abstention` owns the user-visible limitation and next step.
- **Plain Spanish and a code-added notice.** The lead-in and the orientative
  notice are pinned strings added by code; neither contains a digit or a date.

Run the grounded-generation report over the synthetic fixtures (it prints each
material claim with its cited candidate numbers and its grounding verdict):

```sh
python3 backend/scripts/evaluate_generation.py \
  --catalog backend/tests/fixtures/generation/catalog.json \
  --passages backend/tests/fixtures/generation/passages.json \
  --eval backend/tests/fixtures/generation/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

Exit codes: `0` report produced with every grounding invariant holding, `1` a
grounding invariant failed (ungrounded claim, unknown or undeclared marker, a
non-literal critical claim, or an eligibility claim) or, only with
`--fail-on-miss`, a question whose outcome differed from its `expect` value,
`2` an unreadable or invalid input. With an empty catalog and no passages the
command reports zero candidates and zero answers.

**Reviewer guidance.** A passage's `text` is what a user reads: the extractive
generator quotes the reviewed excerpt verbatim as the answer claim, so keep
excerpts short, self-contained, single-sentence, and understandable without
surrounding context. Avoid legal-status phrasing in an excerpt (for example
`tienes derecho a`), because such a claim is rejected rather than shown. A
multi-sentence excerpt also fails closed under the per-sentence citation rule.
Passage ids used in an evaluation file must exist in the built index; a line
naming an unknown id is a harness error (exit `2`), not a silent miss.

## Reviewed safety evaluation cases (`land-safety-eval-v1`)

`land_safety_eval.schema.json` is the readable contract for the reviewed,
source-anchored safety evaluation set; `backend/app/land_safety_eval.py` is the
executable validator and offline harness, and the two must stay in sync. A case
set is a Git-tracked, human-reviewed artifact: it exercises the trap taxonomy
(out of corpus, land ambiguity, false premise, unknown attribute) and checks
that the accepted end-to-end decision still cites the right sources, still
abstains safely, still asks for the right land, and still does not invent a
value. It never asserts a real legal fact.

```json
{
  "schema_version": "land-safety-eval-v1",
  "cases": [
    {
      "id": "covered-solicitud-unica-01",
      "category": "covered",
      "question": "¿Pregunta sintética de ejemplo?",
      "land_context": { "mode": "general", "lands": [] },
      "expect": "answered",
      "expected_source_ids": ["fixture-src-a"],
      "expected_passage_ids": ["fixture-passage-a1"],
      "critical": false,
      "review": null
    }
  ]
}
```

| Field | Rule |
|---|---|
| `schema_version` | Must be `land-safety-eval-v1`. |
| `cases` | Array of case objects; may be empty (the harness then only reports a corpus summary). |
| `id` | Unique, stable lowercase slug. Never reuse it. |
| `category` | One of `covered`, `uncovered`, `mixed_land`, `unknown_attribute`, `false_premise`. |
| `question` | The synthetic, reviewed question, sent to the accepted decision verbatim. Non-blank. |
| `land_context` | The accepted `AskRequest.land_context`: only `mode` (`general`/`all_active`/`selected`) and `lands`; each land carries only its opaque `id` plus the needed `municipality`/`water_regime`/`production_method`. A name, note, area, timestamp, or any other key is a load error. |
| `expect` | One of `answered`, `abstained`, `needs_land_clarification`. |
| `expect_reason` | Required when `expect` is `abstained`: one of the nine accepted abstention reasons. |
| `expected_source_ids` | Required (non-empty) when `expect` is `answered`: every catalog source id the answer must cite. |
| `expected_passage_ids` | Optional narrowing: every listed reviewed passage id must appear among the returned sources. |
| `expected_land_ids_to_choose` | Required (non-empty) when `expect` is `needs_land_clarification`: exactly the ids the clarification must offer, drawn from the request. |
| `critical` | Optional boolean (default `false`). |
| `review` | `null`, or `{ "reviewed_by", "reviewed_on" (YYYY-MM-DD), "level" (int ≥ 1), "anchor" ("<source_id>#<location>") }`. Required and non-null when `critical` is `true`. |

Unknown keys, duplicate ids, an unknown category or expectation, a missing
conditional field, and a critical case without a completed `review` are located
load errors (exit `2`, path such as `$.cases[0].expected_source_ids`).
Diagnostics never print case text.

### Procedure for adding a safety case

1. Write the question in plain Spanish against the *current* corpus and decide
   which trap-taxonomy category it exercises.
2. Name the reviewed `expected_source_ids` (and, when useful, `expected_passage_ids`)
   for an answered case, the `expect_reason` for an abstained case, or the
   `expected_land_ids_to_choose` for a clarification. Run the harness and confirm
   the outcome matches for the right reason, not by accident.
3. For a `critical` case (a deadline, an amount, a threshold), open the cited
   source, verify the fact by hand, and record a completed `review` block whose
   `anchor` is `<source_id>#<location>`. The harness records this provenance but
   never verifies the fact: **a human must**.
4. Open a pull request; a reviewer other than the author approves the case before
   it is merged. A case that only makes a fixture pass, or that asserts a real
   legal fact the corpus does not support, is rejected.

The harness runs the accepted decision unchanged and reports the metrics
report-only. Thresholds (`MasterPlanV3` §9.2 proposes `hit@5 85%`, correct
abstention `100%`, invented numbers/dates `0`) are **inherited proposals, not
enforced gates**, and the synthetic corpus is not legal-coverage evidence.

### Running the safety evaluation

From the repository root:

```sh
python3 backend/scripts/evaluate_land_safety.py \
  --catalog backend/tests/fixtures/land_safety/catalog.json \
  --passages backend/tests/fixtures/land_safety/passages.json \
  --cases backend/tests/fixtures/land_safety/cases.json \
  --as-of 2026-10-13 --k 5
```

`--passages` and `--cases` are optional. `--json` emits the same report as JSON
(byte-identical between runs); `--fail-on-miss` opts into a non-zero exit when a
case does not meet its expectation (off by default). Exit codes: `0` report
produced and every safety invariant held, `1` a payload leaked or invented
something, or (only with `--fail-on-miss`) a case missed its expectation, `2` an
unreadable or invalid input. No command here performs network access.
