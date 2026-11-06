# Validation: `legal_structure_chunker`

Verdict: **accept** (independent validator, 2026-11-07; validator accept is final by owner
decision, no owner walkthrough).
Spec: [legal_structure_chunker.md](../specs/legal_structure_chunker.md). Evidence: appendix
"Feature evidence".

## Checks rerun
- `./scripts/init.sh --feature legal_structure_chunker`: `28 passed`; `--check-contract` printed the
  `legal-chunk-set-v1` + `legal-chunk-manifest-v1` line; two-root `diff -r` identical.
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend `2069 passed, 5 skipped`).
- `--verify` not rerun: the diff touches only `backend/`, `knowledge/` and docs, with no `shared/`,
  Android, Gradle or packaging inputs.

## Findings
- Determinism beyond the tier: the same fixture run under `PYTHONHASHSEED=0/1/12345` produced
  byte-identical trees; LF only, one trailing newline; a rerun into the same root left mtimes
  unchanged.
- Scenarios probed directly: a pipe-table row beginning `Artículo 14.` is `unstructured` with
  `no_structure_headings` and no artifact; prose `Artículo 14 de la presente Ley` stays in the body;
  a header-only chapter emits no chunk but remains in later paths; the preamble is `Documento` with an
  empty path; an unmatched catalog yields `unknown` with `catalog_source_unknown` and no derived
  dates; header-only segments do not become chunks.
- Fail-closed: wrong schema version or unknown key → `invalid_manifest`; candidate/directory mismatch
  → `candidate_mismatch`; missing Markdown → `missing_markdown`; hash or byte mismatch →
  `markdown_hash_mismatch`; inconsistent page map → `page_map_mismatch`; the previous artifact stays
  byte-identical and other documents are processed; exit `1`. Unsafe, equal, nested or `knowledge/`
  output roots, missing roots, an invalid catalog, and more than 1,000 manifests exit `2` with
  `{"error": "ChunkerError"}` and write nothing. The 8 MiB, 2,000-chunk and 8,000-character bounds
  behave as specified.
- Catalog-only validity: fixed `CATALOG_AS_OF = date.min` (never the wall clock); an already-past
  `valid_until` still joins and is copied verbatim; no value comes from document text.
- No canonical or answer-path change: `knowledge/` bytes and parser fixtures are identical after
  runs; no answer-path module imports the chunker; output carries no `review_status`; only the schema
  file is added under `knowledge/`.
- Durable docs match reality: ARCHITECTURE line, constraint MUST, `backend/README.md` section,
  `knowledge/README.md` row and sentence, limitation plus PROGRESS digest, and appendix evidence.

## Low, non-blocking notes
- Discovery globs `parse-*.json`, so an unrelated `parse-notes.json` would be reported `failed`
  (invalid or candidate mismatch) and exit `1` instead of being ignored as the spec's "other files
  ignored" suggests. No real parser path writes such a file.
- A hypothetical pipe-less table row beginning `Artículo 14. Objeto | …` would split; every table the
  accepted parser emits starts with `|`.

## Unverified claims and limits
- No owner walkthrough: backend-only developer command with no UI surface.
- Heading detection is a conservative Spanish line-shape rule limited to `Artículo`, `Capítulo` and
  `Anexo`; `Título`, `Sección`, `Disposición` and `Preámbulo` never split, and a heading written in
  another shape is missed rather than guessed.
- Validity is only as reviewed as `knowledge/source_catalog.json`; unmatched documents stay `unknown`.
- Chunk sets stay derived review input outside `knowledge/`; nothing becomes answerable knowledge.
