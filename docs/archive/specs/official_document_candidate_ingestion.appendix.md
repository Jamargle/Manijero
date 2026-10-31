# `official_document_candidate_ingestion` planning appendix

## Repository research

Current system is a FastAPI service using the reviewed knowledge catalog, offline BM25 retrieval, deterministic extractive answer generation, and strict draft verification. The canonical knowledge directory requires human approval. Current source set and evaluation scope are documented in `knowledge/README.md`, `knowledge/pac_coverage.md`, and `docs/validations/backend_answer_evaluation.md`.

`official_source_discovery` is the upstream producer for newly listed publication candidates and the only source of publication URLs for this feature. Configured monitoring feeds are read only to report their document-coverage gap; they retain snapshots, not document URLs, so they contribute zero candidates. This feature does not perform web discovery itself. The canonical source catalog remains the admission gate.

## Implementation plan

1. Inspect monitor/discovery candidate formats, the catalog validator, and focused command before changing code.
2. Fetch only candidate URLs with a verified approved issuer and exact approved HTTPS host; fail closed on missing provenance.
3. Preserve original bytes/digests and source-registry provenance, then parse supported document formats into quarantined output.
4. Add representative and adversarial fixtures for unsafe destinations, malformed/oversized payloads, duplicate candidates, unavailable origins, and parse failures.
5. Capture reproducibility, resource, and evaluation evidence; update operator documentation and status.

## Validator checklist

- Existing `/ask` contract, citation mapping, campaign/validity filtering, and abstention behavior remain valid.
- Provenance and failure states are inspectable; secrets and personal/land details are absent from logs.
- Canonical knowledge is never changed without human approval.
- Evidence supports only the exact scope claimed.

## Feature evidence

### Implementation

- `backend/app/document_ingestion.py` implements the ingestion command path:
  discovery/monitoring state loading, strict admission, bounded fetch, HTML/PDF
  extraction, quarantine writes, per-candidate failure isolation, atomic state
  writes, and a deterministic report. It is standard-library only.
- Admission requires `review_status: pending`, a known approved issuer, and an
  exact issuer host from `app.source_catalog.ISSUER_ALLOWED_HOSTS`; the URL must
  be HTTPS with no credentials, non-443 port, site root, or fragment.
- Redirects are followed only when each hop stays on HTTPS and on an exact host
  approved for the same issuer, capped at three hops. All other redirects,
  changed unsupported final URLs, non-200 responses, oversize bodies,
  unsupported/mismatched content types, and parse failures fail closed with a
  fixed category.
- The original bytes and their SHA-256 are preserved in quarantine under
  `<quarantine>/<candidate_id>/original-<sha256>.<pdf|html>`; extracted blocks
  are written to `extracted-<sha256>.json` with `Página N` (PDF) or heading-path
  (HTML) sections. Every record keeps `review_status: pending`.
- PDF extraction handles uncompressed/Flate streams, literal and hex strings,
  UTF-16BE/LE string BOMs, PDF 1.5 object streams, multiple page content
  streams, and embedded-font `ToUnicode` CMaps (`bfchar`/`bfrange`/array
  ranges). Blocks containing only `U+FFFD` are dropped; a document with no
  remaining text fails as `no_extractable_text`.
- `backend/scripts/ingest_official_documents.py` is the operator CLI; exit `0`
  means no candidate failed or was rejected, `1` means at least one did, and
  `2` means a config/state file was invalid, more than 1,000 candidates were
  present, or an unexpected exception escaped before a report. Error output is
  the exception type only, not upstream text, paths, or a traceback.
- `backend/tests/test_document_ingestion.py` adds 36 focused tests (plus
  fixtures under `backend/tests/fixtures/document_ingestion/`) covering
  admission, redirect policy, the 500-page/20,000-object boundaries, 501-page
  and 20,001-object failures, type/body mismatch, malformed and textless PDFs,
  duplicate candidates/content, unchanged reuse, extractor-revision
  re-extraction, state preservation, knowledge-path rejection, monitoring
  coverage reporting, schema validation, and CLI exit/error redaction.
- `knowledge/official-ingestion-state.schema.json` and
  `knowledge/official-ingestion-document.schema.json` publish the quarantine
  contracts; `knowledge/README.md`, `backend/README.md`, `ARCHITECTURE.md`, and
  `PROGRESS.md` document the command, boundary, and limits.

### Verification (2026-10-27)

```sh
MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_document_candidate_ingestion
# 672 passed, 1 warning in 7.94s
# warning: StarletteDeprecationWarning (httpx/testclient), unrelated to this feature

./scripts/init.sh --fast
# All 9 offline checks passed.
# Fast tier passed.

cd backend && .venv/bin/python -m pytest tests/test_document_ingestion.py -q
# 36 passed in 0.21s
```

`./scripts/init.sh --verify` was not run: this feature is backend-only and does
not change the shared/Android/Desktop surface, packaging, the HTTP contract, or
the answer path. The focused and fast tiers cover the changed code.

### Live smoke (2026-10-27)

An end-to-end CLI run used a temporary `official-discovery-state-v1` file with
the two real publication URLs below, a temporary state/quarantine directory
outside the repository, and the venv CA bundle only to fix the host trust store:

```sh
SSL_CERT_FILE="$PWD/backend/.venv/lib/python3.14/site-packages/certifi/cacert.pem" \
  backend/.venv/bin/python backend/scripts/ingest_official_documents.py \
  --discovery-state "$TMP/discovery.json" \
  --state "$TMP/state.json" \
  --quarantine "$TMP/quarantine"
```

Result: exit `0`; summary `extracted: 2, failed: 0, rejected: 0`.

| Candidate | Transport | Bytes | SHA-256 (prefix) | Pages | Blocks | Characters | `U+FFFD` |
|---|---|---|---:|---|---:|---:|---:|---:|
| `BOE-A-2026-22454` (`https://www.boe.es/boe/dias/2026/10/27/pdfs/BOE-A-2026-22454.pdf`) | `200` | 216,494 | `d9171daf4c871928` | 2 | 93 | 4,179 | 0 |
| `BOJA26-001-00035-17442-01_00331039` (`https://juntadeandalucia.es/eboja/2026/1/BOJA26-001-00035-17442-01_00331039.pdf`) | `307` → `https://www.juntadeandalucia.es/...` → `200` | 756,455 | `9ef939b3dcfce748` | 35 | 1,767 | 80,388 | 5,041 (6.27%) |

The BOJA redirect is the same-issuer no-`www` → `www` case; it succeeds under
the bounded redirect policy. The BOJA text loss comes from incomplete subset-font
`ToUnicode` maps, not from redirect handling. The first live attempt with the
default platform trust store raised `CERTIFICATE_VERIFY_FAILED` while `curl`
succeeded; setting `SSL_CERT_FILE` to the existing `certifi` bundle fixed it.
Certificate verification was not disabled.

### Limit and extractor-revision repro (2026-10-27)

A standalone in-process run used temporary discovery/state/quarantine
directories and stubbed the fetcher with synthetic PDFs (no repository writes):

```text
501-page synthetic PDF       -> failed  size_limit_exceeded
20,001-object synthetic PDF  -> failed  size_limit_exceeded
older extractor (v0) record  -> extracted on the next run
  last_success_at 2026-10-27T12:00:00+00:00 -> 2026-10-28T12:00:00+00:00
  attempts 2, original and extracted files present
```

The limit cases fail before extraction returns a document, and the extractor
case re-fetches and advances the state rather than treating the old record as
current.

### Boundary and failure evidence

- Tests assert `knowledge/source_catalog.json` and `knowledge/passages.json`
  SHA-256 values are unchanged by an ingestion run, and that state/quarantine
  paths inside the repository `knowledge/` directory are rejected with
  `unsafe_workspace` before any write or fetch.
- Redirect tests reject `http`, cross-issuer/lookalike hosts, credentials, site
  roots, fragments, non-443 ports, and more than three hops; a same-issuer
  no-`www`/`www` redirect is accepted.
- Invalid state files fail before any network access and before overwriting the
  existing state; a failed attempt preserves the previous good extraction and
  last-success time.
- Duplicate candidate URLs and duplicate document bytes inside one run are
  reported, not ingested twice.
- Monitoring state contributes zero fetchable candidates and is reported as
  `unchecked / no_document_candidates` instead of guessed document URLs.
- The CLI reports only the exception type for invalid input and unexpected
  exceptions (exit `2`), with no path, upstream text, or traceback; state and
  logs use fixed failure categories only.
- Explicit limit tests cover 501-page and 20,001-object payloads failing as
  `size_limit_exceeded`, and 500-page / 20,000-object payloads extracting
  successfully.
- An older stored `extractor` value re-fetches and re-extracts, advances
  `last_success_at`, and preserves `previous_original_sha256`. Original bytes
  remain hashed per version; when the original bytes are unchanged, the
  same-named `extracted-<sha256>.json` is replaced by the new extraction rather
  than kept alongside it.

### Honest limits and residual risk

- No OCR. Scanned/image-only PDFs fail as `no_extractable_text`; OCR remains a
  separate, unmeasured feature.
- No LZW/ASCII85/encrypted PDF support; these fail closed.
- Incomplete subset-font `ToUnicode` maps can omit glyphs or leave `U+FFFD`
  placeholders (observed at 6.27% on one BOJA PDF). Extraction is line-level,
  does not reconstruct paragraphs, and is not an accuracy guarantee.
- HTML extraction preserves heading structure but is not a browser rendering.
- `page_count` counts PDF pages that produced at least one text block, not the
  document's declared page count; textless pages are absent from that count.
- Monitoring feeds themselves are not treated as document candidates; the
  discovery state remains the input for publication URLs.
- Discovery's `version_hash` covers title and URL only, so bytes replaced at a
  stable URL are not detected without a refetch. An extractor revision triggers
  a refetch/re-extraction, not an offline re-extraction from preserved bytes; if
  the upstream is unavailable, the revision cannot be applied until it returns.
- The quarantine grows with every changed version and is never garbage-collected.
  The command has no lock, so one state/quarantine pair must have a single writer.
- The state file is validated structurally and file-presence paths are constrained
  to the candidate's quarantine directory, but the remaining provenance values
  are trusted operator input rather than independently re-verified.
- No scheduled dispatch, human review UI, passage extraction into the canonical
  corpus, reindexing, or release automation. Nothing quarantined is answerable,
  and no legal-coverage or answer-quality claim follows from a successful run.
- Live smoke covers two documents on one date, not a corpus-wide measurement.
  Reviewers must compare original and extracted copies before proposing any
  canonical change.
- The documented 15-second timeout is a per-operation socket/read timeout, not a
  total wall-clock cap; a slow-drip response can exceed it.

### Acceptance

Independently accepted on 2026-10-27 after one `revise` cycle; the verdict, the
reproduced checks, the accepted limits, and the recorded follow-ups are in the
[acceptance record](../../validations/official_document_candidate_ingestion.md).
