# Validation: `rag_demo_rehearsal`

Verdict: **accept** (independent validator, 2026-11-06; the condition "pending owner walkthrough" was
met 2026-11-07: the owner ran `docs/demo-script.md` and reported every step matched). At validation the
live `--demo-rehearsal` run and the manual app steps were not run during validation). Spec:
[rag_demo_rehearsal.md](../specs/rag_demo_rehearsal.md). Evidence: appendix "Feature evidence" and
"Validator checklist". The orchestrator later ran the live command against `--local-rag-start`
(4 `PASS`, exit 0, twice); the app-only steps remain unwatched.

## Checks rerun
- `./scripts/init.sh --feature rag_demo_rehearsal`: focused tier passed unchanged (2 published
  command lines; `bash -n` plus `tests/test_demo_rehearsal.py` — 11 passed).
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed (backend 1882 passed, 4 skipped;
  harness 20 passed; contract, catalog, retrieval, generation, abstention, clarification,
  land-safety evaluators 0 differing).
- `--verify` not rerun: the diff touches no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or
  packaging file; it only names existing pinned strings.
- `git status --short`: only the expected files; no service, `contracts/`, `knowledge/`, app, or
  dependency change.

## Findings
- Command contract: `--demo-rehearsal` sits in the early owner dispatch before the
  `local.properties` write, refuses a second argument with one sentence and exit `2` before any
  request or write, links `backend/.venv` like `--local-smoke`, and `exec`s the stdlib-only script;
  `usage` and the `--check` listing are updated.
- Steps match scenarios 1–3: `/health` `ok` + `/ready` `ready`; grounded answer requires `answered`,
  non-empty answer, ≥1 source, every URL in the approved catalog with one in campaign 2026,
  `land_scope == "general"`, and a cited passage when `inspection` is present; the trap requires
  `abstained`, empty `sources`, non-empty answer, and a known `ABSTENTION_REASONS` code when
  `inspection` is present. Unreachable/503 skip the service steps, a failing step does not stop the
  others, and exactly one `Result:` line names failures/skips plus the `--local-rag-start` fix;
  exit `0`/`1`/`2`.
- Review gate: real `review_package.prepare` → unapproved `merge` (must raise
  `approval_required`) → `record_decision` by the synthetic `Revisora de ensayo` → `merge` with the
  same case file, inside one `mkdtemp` copy of `change_impact` removed in `finally`; passes only on
  `ready_for_review`, zero failed checks, the new source/passage ids, and byte-identical canonical
  `knowledge/source_catalog.json` and `knowledge/passages.json`.
- Safety: requests are `land_context.mode = "general"` with no lands and
  `retain_for_improvement: false`; default address is loopback `${MANIJERO_LOCAL_RAG_PORT:-8000}`;
  `sys.dont_write_bytecode` keeps `__pycache__` out of `backend/app`; output carries fixed labels,
  reason codes, source counts, and the address only — tests assert the fixed questions, both answers,
  and the synthetic passage text never appear.
- Docs: `docs/demo-script.md` is plain Spanish, in order, marks every app step manual, gives the
  missing-`Inspeccionar` fallback, declares the synthetic update, and promises no land clarification,
  legal conclusion, eligibility, coverage, quality, or latency claim; the three named topics match
  `knowledge/pac_coverage.md`. Owner-guide expected lines and failure table match the printed
  strings; the pinned copy (`No tiene en cuenta tus terrenos.`, `Sin respuesta segura`,
  `Inspección de la respuesta`) exists in commonMain and `started at http://127.0.0.1:8000.` matches
  `local_rag_service`. `ARCHITECTURE.md` gains one boundary bullet and
  `docs/constraints/operations.md` one MUST; no fact is duplicated across them.
- Security checklist: no credentials or tokens sent or printed, no non-loopback default, no writes
  outside the removed temporary workspace, no request/answer text logged. No findings.

## Remaining limits
- A pass proves reachability, grounding-with-approved-sources, abstention, and the review gate for
  the two fixed questions; it proves no answer quality, legal coverage, or general accuracy.
- The validator did not run the real stack. The orchestrator did, after validation: two
  `--demo-rehearsal` runs against `--local-rag-start` printed the four `PASS` lines and the passing
  `Result:` (exit 0), and `knowledge/` stayed clean. The source cards with the pinned scope caption,
  `Sin respuesta segura`, and the `Inspeccionar` walkthrough remain unwatched and are the owner
  walkthrough in `docs/owner-guide.md`.
- `PROGRESS.md`, `docs/progress/known-limitations.md`, `docs/progress/session-log.md`, and the
  `feature_list.json` status to `accepted` are pending the owner walkthrough report.

## Owner walkthrough
- 2026-11-07: the owner went through `docs/demo-script.md`, including the app-only steps (source cards
  with the scope caption, `Sin respuesta segura`, `Inspeccionar`); everything matched. Acceptance is an
  evidence-only update; no second validator run.
