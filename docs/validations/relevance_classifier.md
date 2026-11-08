# Validation — `relevance_classifier`

## Verdict

**Accept** — 2026-11-08. Independent validation of the uncommitted implementation against
`docs/specs/relevance_classifier.md`. Per the owner, a validator accept is final; no owner walkthrough.
Recommended state update: orchestrator may set `status` to `accepted`.

## Checks rerun

- `./scripts/init.sh --feature relevance_classifier`: 269 passed (new, local-generation, procedure-map, discovery tests).
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed (backend 2552 passed, 7 skipped).
- `--verify` not rerun: no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging change.

## Spec review

- Scenario 1/6: rows sorted by `candidate_id`, canonical JSON, no timestamp, input SHA-256s, model tag/digest, atomic write.
- Scenario 2: `scan_text(title_like=True)` on title and issuer; `prompt_injection` / `nominal_listing` skip the model with `unsure`, `topic: null`. System message is fixed instruction plus topic list; user message is only `{"candidate":{issuer,title}}`.
- Scenario 3: strict parser is the authority (exact keys, label and topic in vocabulary); transport errors map to `model_error`; no model text stored or printed.
- Scenario 4: 500-char bound (title and issuer) with `truncated`; more than 5,000 candidates aborts `candidate_count_exceeded` before writing.
- Scenario 5: report is written only after all candidates succeed; path inside `knowledge/` or equal to an input aborts `unsafe_report_path`; `connection_refused` / `model_not_found` / `model_digest_mismatch` abort `model_unavailable`.
- Scope: the only change to existing code is the `response_format` keyword in `local_generation.py` (default unchanged). The CLI imports no `app.main`, `ask_api`, or retrieval. Model record, `knowledge/` data, `contracts/`, and `init.sh` are untouched.
- Docs: ARCHITECTURE bullet, constraint MUST, risk entry, backend/knowledge README, and schema file are present.

## Security

No findings. Candidate text is data-only, malformed output fails closed, the endpoint is loopback via the existing transport, there are no new dependencies, and nothing reaches the corpus, releases, indexes, or `/ask`.

## Limits that remain

- Accuracy of the local model is unmeasured; the artifact says so.
- A reworded injection that `corpus_security` does not flag can still sway a real model within the label/topic vocabulary (recorded in the risks doc).
- Only titles and issuers are classified.
