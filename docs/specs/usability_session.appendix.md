# usability_session — appendix

## Repository research

### Files inspected

- `feature_list.json` — entry `usability_session` (`evaluation`, `not_started`, depends on `local_end_to_end_smoke`, `welcome_first_use`).
- `PROGRESS.md` "Current state" — QA deployed on the owner's Mac (`qa_server_deployment`), QA test builds (`--desktop-qa`), welcome card accepted without owner walkthrough.
- `docs/constraints/operations.md` — one named command, prerequisite check, one `Result:` line, confirmation before replacing data, owner-guide walkthrough rule.
- `docs/constraints/hosting-and-pilot.md` — QA is made-up test data only; pilot profile with metadata-only logging.
- `scripts/init.sh` — early owner-command dispatch (`--demo-rehearsal` lines 278-294 is the closest pattern), `usage` (~line 387), `--check` listing (~line 964), verify-block parser for `--feature`.
- `docs/specs/rag_demo_rehearsal.md` + archived appendix — owner-command plus plain-Spanish run-sheet shape; same `applicability` limit on land clarification.
- `docs/specs/local_load_test.md` — results written outside the checkout under an environment home, mode `0600`, aggregate-only output.
- `docs/owner-guide.md` — English, numbered steps, expected `Result:` lines, "If ... shows something else" tables; walkthrough sections (`Owner walkthrough: local smoke test`, `... QA`).
- `backend/app/input_guardrails.py` — `screen_question` returns `personal_data` first (DNI, NIE, NIF, phone, email, IBAN; SIGPAC/cadastral masked); names and addresses are not screened.
- `backend/app/qa_deployment.py` (`_confirm`) and `backend/app/local_rag_bootstrap.py` (~line 1280) — injected prompter; `yes` confirmation; `None` on end of input.
- `backend/app/local_rag_bootstrap.py` — `MANIJERO_LOCAL_HOME` test-only override pattern; homes must be outside the checkout.
- `shared/src/jvmMain/.../platform/DesktopEnvironment.kt` — QA Desktop keeps its data in `~/.manijero-qa` (lands, welcome flag, connection), apart from the normal app.
- `shared/src/commonMain/composeResources/values/strings.xml` — pinned labels quoted by the kit (welcome, add land, clarification, scope captions, sources, remove/delete, `Ver bienvenida`).
- `docs/specs/welcome_first_use.md` — `Ver bienvenida` shows the card again in chat (usable as the between-participant reset).
- `knowledge/pac_coverage.md` — no `applicability`; `alcance-terrenos` answers the same for all lands, so no clarification on QA.
- `docs/risks-and-open-questions.md` line 53 — the open usability-evidence risk this feature eventually closes.
- `.gitignore` — existing "guard against an accidental copy" pattern (`*.token`, `pilot-clients*.json`).

### Existing patterns to follow

- Owner commands live in the early `init.sh` dispatch, reject extra arguments with `Run %s on its own, with nothing after it.` and exit `2`, and resolve `backend/.venv/bin/python` via `scripts/python-env.sh dev --if-present`.
- Operator modules take injected ports (out, prompter, paths) so tests drive them in-process; subprocess tests pass temporary homes.
- Data written for the owner goes outside the checkout, atomically, with private modes.

### Current gaps

- No kit, recorder, results file, or owner section exists.
- QA cannot trigger `needs_land_clarification` on the approved corpus (task 3 handled as scenario 3).
- No reset command for the QA Desktop app; reset is by hand (contract scenario 4).

## Fixed kit values (planner decisions)

- Land card A: `Nombre del terreno` `Olivar de prueba A`; `Zona o paraje` `Paraje inventado`; variety `Picual`; `Regadío`; surface `2`. Land card B: `Olivar de prueba B`; `Camino de ensayo`; `Hojiblanca`; `Secano`; leave the rest blank or `No lo sé`. Both cards say «Datos inventados. No escribas datos reales.»
- Task 3 card question: `¿Hasta cuándo puedo presentar la solicitud única de 2026 para mis terrenos?` (answerable from the reviewed deadline passage; contains no personal data).
- Help rule: help only after the participant asks or after 2 minutes without progress → `Necesitó ayuda`. Give-up rule: participant says so, or 5 minutes → `Abandonó`. Time in whole minutes from reading the card to finishing.
- Facilitator neutrality: read the card aloud, no pointing at the screen, ask "¿Qué piensas que pasa ahora?" instead of explaining.
- Debrief questions (5): what was easiest; what was hardest or confusing; would they trust where the answer comes from and why; what they would tell a neighbour about the app; anything they missed. Answers summarised by the owner in small letters, no names.
- Paper sheets: no names; after recording, keep or destroy the sheet (it holds only the code).
- Recorder task ids: `first_use`, `add_two_lands`, `land_question`, `sources`. Outcome input `1|2|3` → `completed|needed_help|gave_up`. Land-choice input `y|n` (also `sí|si|no`).
- App-word allowlist (capitalised words allowed in notes): `Manijero`, `QA`, `Asistente`, `Ayuda`, `Mis`, `Terrenos`, `Añadir`, `Guardar`, `Entendido`, `Fuentes`, `Fuente`, `Publica`, `Abrir`, `Quitar`, `Borrar`, `Continuar`, `Preguntar`, `Elige`, `Conexión`, `PAC`, `SIGPAC`, `FEGA`, `Junta`, `Andalucía`, `Picual`, `Hojiblanca`, `Secano`, `Regadío`, `P1`-`P99`. Name cues: `se llama`, `me llamo`, `llamado`, `llamada`, `apellido`, `don`, `doña`, `señor`, `señora`, `sr.`, `sra.`. Address cues: `calle`, `c/`, `avenida`, `avda`, `plaza`, `portal`. Digit rule: 5+ consecutive digits.
- Fixed sentences: code refusal `Use the code from the sheet, like P1. Do not type names.`; note refusal `That note may hold a name, phone number, email, address, or ID. Write it again without personal details, in small letters (app words such as Ayuda may keep their capital).`; result lines as in contract scenarios 5-7.

## Implementation plan

1. Write the five kit files in plain Spanish (each about 25-60 lines; facilitator script the longest) with the fixed values above.
2. Add `backend/app/usability_results.py`: constants, `validate_code`, `screen_note` (returns a refusal kind or `None`, never the text), record dataclasses, `load`/`save` (atomic, `0600`/`0700`, schema check), `summary_lines`.
3. Add `backend/scripts/usability_record.py`: resolve home (refuse inside checkout), load file, prompt loop with three-tries rule, replace confirmation, recap counts only, `yes` to save, summary, `Result:`; KeyboardInterrupt/EOF → nothing saved.
4. Add `--usability-record` to `scripts/init.sh` dispatch, `usage`, and `--check` listing; add the `.gitignore` guard.
5. Add `backend/tests/test_usability_session.py` (tests below).
6. Update `docs/owner-guide.md`, `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md`.
7. Run the focused block; record the one-line result in Feature evidence.
8. At `passing`: `PROGRESS.md` and `docs/progress/known-limitations.md` one line each. At `accepted` (after the real session): risks row, session-log line, follow-up items.

## Verification plan

- Kit guards: five files exist; consent note states no face/voice recording, no names or personal data kept, made-up land data, can stop, spoken agreement without signature; tasks appear in order 1-4; every quoted label exists in `strings.xml` (format strings matched by their fixed prefix); observation sheet has the three outcome labels, minutes, the land-choice yes/no line, the no-personal-data reminder, and no `Nombre:`/`Teléfono`/`Edad` field; facilitator script names `--qa-status`, `--desktop-qa`, `--usability-record`, and the reset steps; owner guide has the exact section title.
- Recorder happy path: two participants through piped stdin → schema `usability-results-v1`, sorted codes, file `0600`, folder `0700`, summary counts and medians, exact `Result:` lines.
- Refusals: codes `Juan`, `1`, `P0`, `P100`; notes with a capitalised name, each cue word, a phone, an email, a DNI, a NIE, an IBAN, a 5-digit run → refused; the refused text never appears in stdout/stderr or the file. Allowed: app words, SIGPAC-style `23:45:1:12:3`, lower-case notes.
- Three invalid answers → nothing saved, exit `1`. End of input and declined recap → no file / byte-identical file. Replace `P1` with `yes` → replaced; with `no` → unchanged.
- Corrupt or wrong-schema file → unchanged, exit `1`. `MANIJERO_USABILITY_HOME` inside the checkout → refused, nothing written.
- `init.sh --usability-record extra` → exit `2`, no prompt; `init.sh --usability-record` with a temporary home and piped input → saved.
- E2E: no UI automation; the session itself is the end-to-end check and is an owner walkthrough (Notes 7).

## Evidence to capture

- Focused block result (one line) and the test names per behavior.
- Kit file line counts; confirmation that no app label was changed.
- Owner walkthrough (later): number of participants, the summary lines, whether the app ever asked to choose a land, and the follow-up item ids created. No participant details.

## Open questions for the owner (non-blocking)

- Task 3: the land chooser cannot appear on QA with the approved corpus. The kit records "the app did not ask" honestly. If the owner wants participants to see the chooser, a later decision could run that one task against the mock service (`--mock`), which can return `needs_land_clarification`; this spec does not do it (owner decision 3).
- Reset between participants is manual in the app; a reset command for `~/.manijero-qa` would be a separate, owner-approved feature.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-08 (implementer):
- `./scripts/init.sh --feature usability_session`: 66 passed (bash -n init.sh and `tests/test_usability_session.py`).
- `CI=true ./scripts/init.sh --fast`: all 10 checks passed (backend-tests 2582 passed, 7 skipped).
- Tests by behavior: kit guards (5 files, consent, task order, labels vs `strings.xml`, sheet fields, script commands, owner-guide title/size); screening (codes, notes refused/allowed, app words); recorder (two participants, sort, `0600`/`0700`, summary, replace yes/no, 3 refusals, EOF, declined recap, Ctrl+C, corrupt file, home inside checkout, misuse); `init.sh` extra argument exit 2 and piped record with a temporary home.
- Kit lines: guion 57, nota 18, tareas 45, hoja 34, preguntas 13. Owner-guide section 35 lines. No app label, string, or screen changed.
- Status `passing`; the real session (2-3 participants) is still the owner walkthrough that gates `accepted`.

## Validator checklist

- [ ] Owner decisions 1-7 are honoured; nothing fixes a usability finding or changes app/service code.
- [ ] Five kit files exist, plain Spanish, with the consent, task, sheet, and debrief content of scenarios 1-4; labels match `strings.xml`.
- [ ] Task 3 wording is honest about the chooser not appearing; sheet and recorder capture yes/no.
- [ ] `--usability-record` follows the dispatch pattern, ends with one `Result:` line, exits `0`/`1`/`2` as specified.
- [ ] Personal data refusals cover names (code and notes), phones, emails, DNI/NIE/NIF/IBAN, cue words, digit runs; refused text never printed or stored.
- [ ] Results file outside the checkout, `0600`, schema as specified, no dates or identity fields; `.gitignore` guard present.
- [ ] Replace asks `yes`; interrupted/declined/corrupt cases change nothing.
- [ ] Owner guide section titled exactly `Owner walkthrough: usability session`, about 60 lines or fewer, with missing-prerequisite and recovery steps.
- [ ] `ARCHITECTURE.md`, `operations.md`, `backend/README.md` updated within budget.
- [ ] Focused block passes via `./scripts/init.sh --feature usability_session`.
- [ ] Verdict is accept-with-condition; status stays `passing` until the real session is reported.

- Owner walkthrough 2026-11-08: Owner reported the usability session completed successfully on the Desktop QA app with made-up data, results recorded with --usability-record under anonymous codes. Number of participants, per-task outcomes and findings were not reported here; they stay in the owner's local results file (~/manijero/usability/usability-results.json), which agents do not read.
