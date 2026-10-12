# Knowledge: approved source catalog

This directory holds the admission gate for the Manijero MVP knowledge corpus.
A document may only become eligible for ingestion when a human has approved it
and its catalog metadata is complete. The catalog is a Git-tracked text file, so
every addition and change is reviewable, diffable, and revertible.

## What this does and does not do

The catalog and its validator check **catalog policy and metadata**: identity,
provenance domain, integrity digest, dates, human review, and lifecycle state.

They do **not** prove that a document is authentic, currently in force, or
legally applicable. They never fetch a URL, follow a redirect, or inspect the
document body, and they make no legal conclusion. A validated entry means "this
metadata is complete and traceable", not "this rule is the law today".

## Files

| File | Purpose |
|---|---|
| `source_catalog.json` | The canonical, Git-tracked catalog. Currently empty on purpose. |
| `source_catalog.schema.json` | The readable versioned field contract (`source-catalog-v1`). |
| `../backend/app/source_catalog.py` | The executable validator. Must stay in sync with the schema. |
| `../backend/scripts/validate_source_catalog.py` | The offline command-line wrapper. |

`source_catalog.json` starts with `"sources": []`. That is intentional and
valid: the repository has no separately reviewed documents yet. It does not mean
the corpus is broad, current, or ready to answer legal questions.

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
