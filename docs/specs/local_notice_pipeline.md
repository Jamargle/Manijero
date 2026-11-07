# Turn anonymized cooperative notices into vocabulary and candidate questions locally

## Source metadata

- `id`: local_notice_pipeline · `area`: knowledge · `depends_on`: local_generation_provider (accepted), pilot_privacy_readiness (accepted) · `status` at planning: not_started
- User-visible behavior: none in the apps. A developer runs one offline backend command over a folder of anonymized cooperative notices and gets one review file of candidate vocabulary (colloquial term -> standard term) and candidate questions, drafted by the pinned local Ollama model, outside `knowledge/`; nothing it writes becomes answerable.
- Verification: offline pytest with a fake model plus a screen-only CLI run over invented fixtures; the commands are in Focused verification.
- Notes (owner decisions 2026-11-07, fixed):
  1. One offline developer command turns anonymized cooperative notices into a vocabulary list (colloquial term -> standard term) and candidate questions using the local generation provider (Ollama). Notice text is strictly data, never instructions; input is bounded; malformed model output fails closed.
  2. Made-up sample notices only for now: committed fixtures are invented. Real notices come later from the owner.
  3. Before any model call it refuses a notice that still looks like personal data (names with surnames, phone numbers, DNI/NIE/NIF, emails, IBAN, street addresses, cadastral/SIGPAC parcel ids tied to a person) and never retains, logs, or echoes that text.
  4. Output goes to a review folder outside `knowledge/`; nothing reaches the corpus, releases, indexes, eval sets, or `/ask`; a person reviews.
  5. Respect the `pilot_privacy_readiness` rules. Zero cost, no network beyond the local model. Tests run offline with a fake model.
  6. Developer-only: no owner-guide step. Acceptance: validator accept is final, no owner walkthrough.
- Planning interpretation (flag to owner if wrong): a cooperative notice has no legitimate need for a specific parcel, so **any** full SIGPAC reference, 20-character cadastral reference, or `polígono N … parcela M` pair counts as "tied to a person" and is refused.

## Goal

Give the later `question_rewriting` glossary and the evaluation set real olive-grower wording without letting notice text become knowledge: one local, zero-cost command that screens each notice for personal data, asks the pinned local model for colloquial-to-standard term pairs and grower questions, validates every model output strictly, and writes one unreviewed review file for a person to judge.

## Non-goals

- No glossary, rewriting, or `/ask` change (`question_rewriting`); no write to `knowledge/`, catalog, passages, eval sets, releases, indexes, or the procedure map.
- No answers: the model proposes terms and questions only, never answers, dates, or cooperative practices as facts.
- No redaction or anonymization of notices: a notice that looks personal is refused, not repaired.
- No OCR, photo/PDF input, WhatsApp export parsing, notice classification, or relevance scoring (`relevance_classifier`).
- No Gemini or any remote model, no new dependency, no schedule, no `init.sh` mode, no owner-guide step.
- No real notices committed; no claim about extraction quality or detector recall.

## Job story

When I have a handful of anonymized cooperative notices, I want one local command that pulls out the growers' own words and the questions those notices raise, so I can review them as glossary and evaluation candidates without any personal detail or notice instruction leaking into the corpus.

## Acceptance Scenarios

### 1. Clean notices become one unreviewed review file

Given `--notices` holding invented `notice-001.txt`…`notice-003.txt` and a fake model returning valid output · When the command runs with `--output <dir>` · Then `<dir>/notice-review.json` (`notice-review-v1`, `review_status: "unreviewed"`) lists each notice by file name and `notice_sha256` with status `extracted`, its validated `vocabulary` (`colloquial`, `standard`) and `questions`, plus merged, de-duplicated, sorted `vocabulary` and `questions` lists naming their source files, and a `pipeline` block with `instruction_version` and the pinned record's `model` and `digest`; it contains no notice text, timestamp, or absolute path; exit `0`; `knowledge/` is byte-identical.

### 2. Personal-looking notices are refused before any model call, without echo

Given a notice containing any of: a honorific or self-introduction followed by a capitalised name, a common given name followed by a capitalised surname, a phone number, a DNI/NIE/NIF, an email, an IBAN, a street address with number or a postal code, a SIGPAC/cadastral/polígono-parcela reference, or a nominal listing · When the command runs · Then that notice is `refused` with one or more fixed codes (`person_name`, `phone`, `national_id`, `email`, `iban`, `street_address`, `parcel_id`, `nominal_listing`), the fake model is never called for it, and its text, matched value, and hash appear nowhere: not in the review file, stdout, stderr, an exception, or any other file; other notices still run; exit `1`.

### 3. Notice text is data, never instructions

Given a notice with model-directed text (for example "ignora las instrucciones anteriores") · When the command runs · Then it is `refused` with `instruction_like_text` before any model call. Given any clean notice · Then the model receives the pinned instruction (`notice-extract-v1`) as the system message and the notice only inside a JSON-encoded user payload `{"aviso": "<text>"}`, with the JSON schema of the output as Ollama `format`.

### 4. Malformed or unsafe model output fails closed per notice

Given the fake model returns, for one notice: non-JSON, a missing or extra key, a wrong type, more than 15 terms or 5 questions, an over-long or multi-line string, a `colloquial` term that does not occur in the notice (accent-, case-, and space-folded), a `standard` equal to its `colloquial`, a question not ending in `?` or under three words, or any string that trips the personal-data or URL check · When the command runs · Then that notice is `failed` with `model_output_invalid`, none of its output is kept, other notices are unaffected, exit `1`. A model timeout gives `model_timeout` the same way.

### 5. Bounds and unsafe setup abort before writing

Given an output folder inside `knowledge/` or inside the notices folder, a missing notices folder, more than 50 notice files, a non-hidden entry not named `notice-NNN.txt`, an invalid local model record, or `MANIJERO_DEPLOYMENT_PROFILE` set to anything but `development` · When the command runs · Then it exits `2` with `{"error": "NoticePipelineError", "code": "<fixed code>"}` on stderr, makes no model call, and writes nothing; an unexpected entry's name is never printed. Given Ollama refusing the connection, the pinned model missing, or its digest differing · Then it exits `2` the same way and writes nothing, even if earlier notices succeeded. A notice over 16 KiB or 6,000 characters, not UTF-8, or blank is `refused` (`notice_too_large`, `notice_unreadable`, `notice_empty`) without a model call.

### 6. Screen-only mode needs no model

Given `--screen-only` · When the command runs over the notices folder · Then it applies scenarios 2, 3, and 5's input checks, prints the same per-notice statuses (`screened` for clean ones), never builds a transport, never opens a socket, writes nothing, and exits `0` only when every notice is clean.

### 7. Offline, reproducible, isolated

Given the same notices and fake model run twice into two output folders · Then both review files are byte-identical (canonical JSON, sorted keys, `indent=2`, LF, one trailing newline). Tests run with sockets blocked. No module on the `/ask`, retrieval, readiness, release, review-merge, or evaluation path imports the new module or reads a `notice-review.json`.

## Technical approach

- New stdlib-only `backend/app/notice_pipeline.py`: folder reader and bounds, personal-data and instruction screen, request builder, strict output validator, merge, canonical writer, report. The only model seam is a `GeminiTransport`-shaped `send(GeminiDraftRequest) -> str`; production builds `OllamaTransport(record, response_format=NOTICE_OUTPUT_SCHEMA)` from `load_local_model_record` + `evaluate_local_model_record` (as-of today); tests inject a fake transport.
- `OllamaTransport` gains one keyword `response_format` defaulting to today's `DRAFT_JSON_SCHEMA` (behavior-preserving); loopback constant, digest check, proxy/redirect refusal, 64 KiB cap, and fixed error codes are reused unchanged. Request: `max_output_tokens` 1024, `timeout_seconds` 120 (an offline per-notice budget, separate from the `/ask` record limit), notices processed sequentially.
- Screen order per notice: bounds and decoding, then personal data, then `corpus_security.scan_text` (`nominal_listing` → personal; `prompt_injection` → `instruction_like_text`). Phone, DNI/NIE/NIF, email, and IBAN reuse `input_guardrails` patterns through one new public function `contains_personal_identifier(text)` (an alias of today's private check, no behavior change); names, addresses, and parcel ids are new code-owned patterns in the new module (rules in the appendix). Parcel rule must not fire on dates (`15-05-2026`, `15/05/2026`) or times (`10:30`).
- Output validation is code-owned and total: exactly `{"vocabulary": [{"colloquial", "standard"}], "questions": [str]}`; caps 15 terms, 5 questions; `colloquial` ≤ 60, `standard` ≤ 80, question ≤ 200 characters; no control characters or newlines; every string re-screened for personal data and URLs. Exact duplicates are dropped, not errors.
- Errors never carry text: every failure maps to a fixed code; the top-level CLI catches everything and prints only the code. The module uses no `logging`.
- Write only at the end: build the whole review in memory, then write `notice-review.json` atomically (temp file + `os.replace`); an abort writes nothing. Suggested output `build/notice-review/` (git-ignored); real notices should live outside the repository.
- CLI `backend/scripts/process_cooperative_notices.py`: `--notices`, `--output` (required unless `--screen-only`), `--screen-only`; stdout is one JSON report (`notices` sorted by file with status and codes, `summary` counts); exit `0`/`1`/`2` as in the scenarios.

## Expected file changes

- `backend/app/notice_pipeline.py` — create; screen, request, validator, merge, writer, report.
- `backend/scripts/process_cooperative_notices.py` — create; CLI and exit codes.
- `backend/app/local_generation.py` — modify; `response_format` keyword on `OllamaTransport` only.
- `backend/app/input_guardrails.py` — modify; public `contains_personal_identifier` alias only.
- `backend/tests/test_notice_pipeline.py` — create; scenarios 1–7.
- `backend/tests/test_local_generation.py` — modify; one test that the default format is unchanged and a passed format is sent.
- `backend/tests/fixtures/local_notice_pipeline/` — create; `README.md` (states every notice is invented), `notices/notice-001.txt`…`notice-003.txt` (clean, invented), `fake_model_outputs.json`. Personal-looking and injected samples are built inside the tests, not committed as files.
- Durable docs below.

## Visual design impact

UI involved: no.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one line near the local generation provider: the notice pipeline is a developer-only consumer of the loopback Ollama transport writing review files outside `knowledge/`, never read by the answer path.
- `docs/constraints/answers-and-knowledge.md`: update, "Knowledge updates and retrieval" — one MUST: cooperative-notice processing is local-model only, refuses personal-looking notices before any model call without retaining, logging, or echoing them, treats notice text as data, fails closed on invalid model output, and writes only unreviewed review files outside `knowledge/` that no answer, release, index, or eval path reads.
- `AGENTS.md`: not needed — no workflow or repo-wide rule change.
- `backend/README.md`: update — one section of at most 30 lines: command, screen-only mode, refusal and failure codes, bounds, exit codes, where to keep real notices.
- `docs/progress/known-limitations.md` + `PROGRESS.md` digest: update — one line: the notice screen is a lexical Spanish heuristic (can miss an unusual name or address, can refuse a cooperative named after a person or saint), tested only on invented notices, no extraction quality measured, output unreviewed.
- `docs/risks-and-open-questions.md`: update — one line: real notices pending from the owner; processing them needs a run on the owner's Mac.
- `docs/owner-guide.md`, `docs/pilot-privacy.md`, `contracts/`, `DESIGN.md`, `CONTEXT.md`, `scripts/init.sh`, `knowledge/`: not needed — developer-only, no pilot participant data flow, wire, UI, domain, or command change.

## Focused verification (required)

<!-- verify:start -->
```sh
PY="${MANIJERO_PYTHON:-backend/.venv/bin/python}"
MANIJERO_PYTHON="$PY" ./scripts/init.sh --backend-tests tests/test_notice_pipeline.py tests/test_local_generation.py tests/test_input_guardrails.py tests/test_corpus_security.py -q
"$PY" backend/scripts/process_cooperative_notices.py --screen-only --notices backend/tests/fixtures/local_notice_pipeline/notices
```
<!-- verify:end -->

No Ollama, no network. The implementer also runs the full `./scripts/init.sh --backend-tests` once as evidence. An optional live run against the owner's local Ollama is recorded in the appendix if done; it is not required for acceptance.

## Appendix

See [`local_notice_pipeline.appendix.md`](local_notice_pipeline.appendix.md) for research, plan, evidence, and the validator checklist.
