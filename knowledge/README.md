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

Retrieval over passages is **lexical and offline** as well. It ranks reviewed
excerpts by word overlap (BM25) and never downloads, parses, or chunks a
document, never reaches a model or the network, and never invents a passage.
`hit@k`/`recall@k`/MRR numbers measured on synthetic fixtures are a starting
measurement, not evidence about legal coverage or real user questions.

## Files

| File | Purpose |
|---|---|
| `source_catalog.json` | The canonical, Git-tracked catalog. Currently empty on purpose. |
| `source_catalog.schema.json` | The readable versioned field contract (`source-catalog-v1`). |
| `passages.schema.json` | The readable versioned passage contract (`passage-set-v1`). |
| `../backend/app/source_catalog.py` | The executable catalog validator. Must stay in sync with the schema. |
| `../backend/app/retrieval.py` | The executable passage-set validator and offline BM25 retriever. |
| `../backend/scripts/validate_source_catalog.py` | The offline catalog command-line wrapper. |
| `../backend/scripts/evaluate_retrieval.py` | The offline retrieval baseline command-line wrapper. |

`source_catalog.json` starts with `"sources": []`. That is intentional and
valid: the repository has no separately reviewed documents yet. It does not mean
the corpus is broad, current, or ready to answer legal questions.

There is deliberately **no canonical `passages.json` yet**. This repository has
no reviewed ingestion/chunking pipeline, so the passage format is exercised only
by synthetic fixtures under `backend/tests/fixtures/retrieval/`. A later reviewed
ingestion feature produces the canonical file. Until then, retrieval over the
canonical catalog returns no candidates.

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
   | `campaign` | Optional non-blank label when the document is campaign-specific. |
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

The baseline runs against synthetic fixtures, because the canonical catalog is
still empty:

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
release gates). `--passages` and `--eval` are optional; with the canonical empty
catalog and no passages, the command reports zero candidates.

Exit codes: `0` report produced, `1` only with `--fail-on-miss` and a miss,
`2` an input file was unreadable or invalid. No command here performs network
access.
