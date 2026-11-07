# Rehearse a scripted RAG demo

## Source metadata

- `id`: rag_demo_rehearsal · `area`: evaluation · `depends_on`: `rag_inspector_view`, `local_end_to_end_smoke`, `knowledge_update_review_pr` (all accepted) · `status` at planning: `not_started`
- User-visible behavior: the owner runs one named command, `./scripts/init.sh --demo-rehearsal`, which drives the service-level demo steps and prints one `PASS`/`FAIL`/`SKIP` line per step plus a final `Result:` line. The live session follows `docs/demo-script.md`, a plain-Spanish run sheet that marks the app-only steps as manual.
- Verification: offline focused tests (fake HTTP service, closed-port path, fixture review package, `init.sh` subprocess); one live run on the owner's Mac with the real local stack. Commands are in Focused verification.
- Notes (owner decisions 2026-11-06, binding):
  1. The deliverable is a plain-Spanish demo script for the live demo plus **one** automated rehearsal command, `./scripts/init.sh --demo-rehearsal`. It drives the service-level steps (grounded answer with sources, trap abstention, reviewed knowledge update) and reports pass/fail with a short summary. The app-only steps (land-scope label, `Inspeccionar` view) are a guided manual walkthrough in the script, not automated.
  2. The live rehearsal runs locally with the existing local service commands. If the full stack is unavailable, the command and the record must state exactly which steps ran and which remain an owner walkthrough.
  3. Demo content comes from the reviewed PAC 2026 corpus and the existing synthetic knowledge-update/review fixtures; anything synthetic is declared synthetic in the script, in the command output, and in evidence.
- Scope note: the feature title also names land clarification. The approved corpus declares no `applicability` (`knowledge/pac_coverage.md`), so the real service cannot return `needs_land_clarification` for it; the spec records this as a known limit and the demo script explains it, rather than adding a fourth automatic step.

## Goal

Give the owner a repeatable, honest way to demo Manijero: one command that proves the service-level chain works before an audience, and one Spanish run sheet that tells the owner what to say, what to click, what is manual, and what the system must not claim.

## Non-goals

- Any change to the answer service, `contracts/openapi.yaml`, `knowledge/`, shared Compose code, app builds, or dependencies. The rehearsal only reads them.
- Starting, stopping, or repairing the service, Ollama, the emulator, or the apps; `--local-rag-*`, `--local-smoke`, `--mock*`, `--android-run`, and `--desktop` keep their behavior.
- Legal conclusions, coverage beyond `knowledge/pac_coverage.md`, answer-quality or latency claims, a general-accuracy claim, or a promise that land clarification appears.
- Real knowledge changes: the reviewed-update step runs on a temporary copy of the synthetic `change_impact` fixtures and never writes `knowledge/`. No reindex, release, deploy, or hosted/QA/prod path.
- A real reviewer identity: the rehearsal records a clearly synthetic reviewer name.
- Answer text, question text, or passage text in command output, logs, or artifacts.

## Job story

When I am about to show Manijero to someone, I want one check and one clear script that tell me whether the chain works and what I must and must not promise, so I do not improvise or over-claim in front of an audience.

## Acceptance Scenarios

### 1. The rehearsal passes on a ready local stack

Given the service started by `--local-rag-start` answers `/health` and `/ready` · When the owner runs `./scripts/init.sh --demo-rehearsal` · Then it prints four passing step lines (reachability/readiness, grounded answer with sources, trap abstention, reviewed update) and one `Result:` line that says the rehearsal passed, names the loopback address, and states that the reviewed update used synthetic fixtures and canonical knowledge was not changed; exit `0`.

### 2. The trap must abstain

Given the same service · When the rehearsal asks the fixed out-of-corpus question · Then it passes only when the response is `status: "abstained"` with an empty `sources` array and a non-empty answer. An `answered` response, a missing key, a non-200 status, or malformed JSON fails that step; the remaining independent steps still run, and the final line names the failing step with exit `1`. The grounded step passes only for `status: "answered"` with at least one source whose URL belongs to the approved campaign-2026 catalog, and `land_scope: "general"`.

### 3. Service unavailable: say exactly what ran

Given no service, an unreachable address, or `/ready` reporting `unavailable` · When the command runs · Then every service step that cannot run prints `SKIP` (not a stack trace), with one line naming the fix `Start it with ./scripts/init.sh --local-rag-start, then run this command again.`; the reviewed-update step still runs offline; the final line says the rehearsal is incomplete and lists the skipped steps; exit `1`. The command starts nothing.

### 4. The reviewed update cannot merge without a named human

Given a temporary copy of `backend/tests/fixtures/change_impact` and the synthetic proposal · When the rehearsal prepares the package, attempts `merge` before any decision, records one approval by the synthetic reviewer, then merges with the same case file · Then preparation is `ready_for_review` with zero failed checks, the first merge is refused with `approval_required`, the second merge writes only the temporary fixture copies, the new source and passage ids are present, and `knowledge/source_catalog.json` and `knowledge/passages.json` are byte-identical before and after.

### 5. The live script is honest and usable

Given `docs/demo-script.md` · Then it is written in plain Spanish and gives, in order: preparation commands, the automated rehearsal, a general question that shows an answer with source cards and the pinned scope caption, a trap question that shows `Sin respuesta segura`, the manual `Inspeccionar` walkthrough (local test build, loopback, `development` only), the synthetic reviewed-update explanation, and a closing limits section. It marks each app-only step as manual, gives a fallback when the inspector is absent, and promises no land clarification, legal conclusion, or eligibility result. `docs/owner-guide.md` gains numbered command steps, the expected `Result:` line, a short failure table of outputs the owner can actually reach, and a pointer to the script.

### 6. Misuse, safety, and no stray writes

Given an extra argument after `--demo-rehearsal` · Then one sentence and exit `2`, with no network call and no files written. On every run: requests use `land_context.mode = "general"` with no lands and `retain_for_improvement: false`; the default address is loopback; the only writes are inside one temporary directory that is removed afterwards; output carries no question, answer, passage, land, or token text.

## Technical approach

- **Command.** `scripts/init.sh` adds `--demo-rehearsal` to the early owner-command dispatch (before the `local.properties`/Gradle block), with the same one-argument misuse check and the same "not set up yet" pair as `--local-smoke`. It resolves `backend/.venv/bin/python` (linking it via `scripts/python-env.sh dev --if-present` when absent) and `exec`s `backend/scripts/demo_rehearsal.py`. Update `usage` and the `--check` listing.
- **Rehearsal CLI.** New stdlib-only `backend/scripts/demo_rehearsal.py` (plus `app` modules only for fixtures/codes) with `--url` for tests/developers; default `http://127.0.0.1:${MANIJERO_LOCAL_RAG_PORT:-8000}`. It makes one `GET /health`, one `GET /ready`, and two `POST /ask` calls with fixed Spanish questions. `/ask` uses the closed request shape from `backend/app/ask_api.py`; timeouts are bounded (short for health/ready, generous for `/ask`).
- **Assertions.** Grounded: `answered`, non-empty answer, ≥1 source, every normalized source URL in the current approved catalog, `land_scope == "general"`. Trap: `abstained`, empty sources, non-empty answer. If the body carries `inspection` (service started by `--local-rag-start` is `development`), a grounded answer must cite at least one passage in `inspection.outcome.cited_passage_ids`, and the trap's `inspection.outcome.abstention_reason` must be a member of `ABSTENTION_REASONS`; an unknown code fails that step. Only the fixed reason code is printed. When `inspection` is absent (`--backend` without the profile), the step still passes on the public fields. Never echo answer or question text.
- **Reviewed update.** Copy the fixture tree into `tempfile.mkdtemp()`, write a synthetic proposal, then call `app.review_package.prepare`, `record_decision`, and `merge` (never `knowledge_review.py` subprocesses, so failures stay typed). Fixed synthetic values are in the appendix. Refuse to pass if preparation is not `ready_for_review`, if the unapproved merge succeeds, or if the approved merge does not add the ids. Compare canonical `knowledge/` hashes around the step.
- **Output and exits.** One line per step (`PASS`/`FAIL`/`SKIP` + fixed English label), then exactly one `Result:` line. Exit `0` all pass, `1` any failure or skip, `2` CLI misuse. No colors, tracebacks, or pasted text.
- **Tests.** New `backend/tests/test_demo_rehearsal.py` runs the CLI as a subprocess against a threaded stdlib fake HTTP service and against a closed port, and invokes `init.sh --demo-rehearsal` for dispatch/misuse. Canonical-hash and request-body assertions cover safety.
- Follow [`local_end_to_end_smoke.md`](local_end_to_end_smoke.md) for the owner-command pattern and [`docs/constraints/operations.md`](../constraints/operations.md) for the one-command/`Result:` rules.

## Expected file changes

- `scripts/init.sh` — modify: dispatch, `usage`, `--check` listing.
- `backend/scripts/demo_rehearsal.py` — create: the four-step CLI and output.
- `backend/tests/test_demo_rehearsal.py` — create: fake-service, closed-port, review-gate, safety, and `init.sh` cases.
- `docs/demo-script.md` — create: plain-Spanish live run sheet (about 80 lines) with manual app steps and honest limits.
- `docs/owner-guide.md` — modify: "Rehearse the live demo" section (steps, expected `Result:` line, failure table, pointer to the script).
- `backend/README.md` — modify: how the rehearsal works, what it asserts, the temporary workspace, and the synthetic declaration.
- `ARCHITECTURE.md` — modify: one bullet for the operator-only rehearsal harness.
- `docs/constraints/operations.md` — modify: one MUST for the rehearsal's read-only/temp-only and synthetic rules.
- `PROGRESS.md`, `docs/progress/known-limitations.md`, `docs/progress/session-log.md` — modify at acceptance: one line each.
- Not changed: `contracts/`, `knowledge/`, `shared/`, `androidApp/`, `desktopApp/`, Gradle files, and the service modules.

## Visual design impact

UI involved: no change. The script refers to existing surfaces and pinned copy only: the `chat_land_scope_*` captions (`No tiene en cuenta tus terrenos.`, `Tiene en cuenta todos tus terrenos.`), `Inspeccionar`, `Inspección de la respuesta`, `Búsqueda`, `Pasajes encontrados`, `Comprobación`, and `Sin respuesta segura`. It adds no screen, string, or baseline.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one sentence/bullet naming the operator-only `demo_rehearsal.py` harness; the service boundary and app wiring do not change.
- `docs/constraints/operations.md`: update — MUST: a rehearsal/check command is read-only for `knowledge/` and owner data, writes only a temporary workspace it removes, sends no land data, and declares synthetic content; reason `rag_demo_rehearsal`.
- `AGENTS.md`: not needed — no workflow, startup-path, or repo-wide rule change.
- Other: `docs/demo-script.md` create; `docs/owner-guide.md` update; `backend/README.md` update; `PROGRESS.md`, `docs/progress/known-limitations.md`, `docs/progress/session-log.md` at acceptance.

## Focused verification (required)

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_demo_rehearsal.py -q
```
<!-- verify:end -->

The live run (`./scripts/init.sh --demo-rehearsal` with `--local-rag-start` running) is the owner walkthrough in `docs/owner-guide.md`, not part of this offline block. If it cannot run in the implementation environment, the appendix records exactly which steps were not run.

## Appendix

See [`rag_demo_rehearsal.appendix.md`](rag_demo_rehearsal.appendix.md) for repository research, plan, evidence, and the validator checklist.
