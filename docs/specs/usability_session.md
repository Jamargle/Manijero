# Run and record a usability session with low-confidence users

## Source metadata

- `id`: usability_session · `area`: evaluation · `depends_on`: `local_end_to_end_smoke`, `welcome_first_use` (both accepted) · `status` at planning: `not_started`
- User-visible behavior: the owner gets a plain-Spanish session kit (facilitator script, consent note, four task cards, observation sheet, debrief questions) for a session on the Desktop QA app, and one named command, `./scripts/init.sh --usability-record`, that saves each participant's results under an anonymous code, refuses personal data, and prints a plain summary ending in one `Result:` line.
- Verification: offline pytest (kit guard checks plus the recorder driven through piped input and an `init.sh` subprocess); the real session is an owner walkthrough. Commands are in Focused verification.
- Notes (owner decisions 2026-11-08, binding):
  1. Deliver a session kit now; the real session happens later.
  2. The kit is in plain Spanish: a facilitator script; a short consent note (no recording of faces or voice, no names or personal data kept; participants use made-up land data only); the four tasks (first-use setup, add two lands, ask a land-dependent question and choose the land when asked, open and understand the sources); an observation sheet (completed / needed help / gave up, time, plain notes without personal data); debrief questions.
  3. The session runs on the Desktop QA app (the owner has no Android device) against QA with made-up test data only.
  4. One named owner command records each participant's results as anonymous participant codes (P1, P2...) into a results file and prints a plain summary, ending with one `Result:` line; it refuses names, phone numbers, emails, DNI-like ids, and free text that looks like personal data.
  5. The owner guide gains a section titled `Owner walkthrough: usability session`.
  6. Tests are offline.
  7. Acceptance: validator accept on the kit (with the condition "pending owner walkthrough / real session"); the feature then stays `passing` until the owner runs a real session with 2-3 low-confidence participants and reports results; only then `accepted`. Findings become follow-up items, not fixes in this feature.
- Scope note: the approved corpus declares no `applicability` ([`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md)), so QA never returns `needs_land_clarification` and the `Elige el terreno de tu pregunta` chooser will not appear in task 3. The kit and the observation sheet handle that honestly (scenario 3); see the appendix open question.

## Goal

Let the owner run a fair, private usability session with people who have little computer experience, and turn what they observe into anonymous, comparable results that can become follow-up items, without any personal data leaving the paper sheet.

## Non-goals

- Running the real session, recruiting participants, or fixing any finding (findings become follow-up items in `feature_list.json` later).
- Any change to the apps, shared Compose code, Spanish UI strings, the answer service, `contracts/`, `knowledge/`, QA commands, or dependencies.
- Android or real-device sessions, local or mock-service sessions, screen or audio recording, signatures, or any participant identity, contact, age, or demographic field.
- A new reset command for the QA app (resetting between participants uses existing in-app steps), a results viewer, export, or upload.
- Usability claims, success-rate targets, or statistics beyond plain counts and median minutes.

## Job story

When I sit down with two or three olive growers who are not used to computers, I want a script, task cards, and a sheet that tell me exactly what to say and note, and one command that stores what happened without their names, so I can show the developer where the app is hard to use without putting anyone's data at risk.

## Acceptance Scenarios

### 1. The kit is complete, plain, and private

Given `docs/usability-session/` · Then it holds five plain-Spanish files: facilitator script, consent note, task cards, observation sheet, and debrief questions. The consent note says the session tests the app and not the person, can stop at any time, records no faces or voices, keeps no names or personal data, uses only the made-up land cards, and asks for spoken agreement with no signature. The observation sheet has a participant-code box (`P1`, `P2`...), and per task `Completada` / `Necesitó ayuda` / `Abandonó`, minutes, and a notes line with the reminder not to write names, phone numbers, or ids; it has no name, contact, or age field.

### 2. Tasks match the real app

Given the task cards and the facilitator script · Then they give, in order: (1) first use: read `Antes de empezar` and close it with `Entendido`; (2) add two lands from the two made-up land cards through `Mis terrenos` → `Añadir terreno` → `Guardar terreno`; (3) ask the land-dependent question on the card about the participant's lands and choose the land when the app asks; (4) open `Fuentes` on that answer, say who publishes the document, and open `Abrir documento oficial`. Every app label the kit quotes exists unchanged in `shared/src/commonMain/composeResources/values/strings.xml`. The script names when to help (participant asks, or two minutes without progress) and when a task counts as given up (participant says so, or five minutes pass).

### 3. Task 3 stays honest when the app does not ask

Given the approved corpus has no land-dependent passages · Then the script tells the facilitator that the app may not show `Elige el terreno de tu pregunta`; in that case the participant completes task 3 by asking the question and pointing to the line saying which lands the answer considered (`Tiene en cuenta todos tus terrenos.`). The observation sheet and the recorder both capture "did the app ask to choose a land: yes / no", and the summary reports it, so no one reads a "yes" that did not happen.

### 4. Preparation and reset use existing commands and app steps

Given the facilitator script · Then preparation is `./scripts/init.sh --qa-status` (QA running), then `./scripts/init.sh --desktop-qa` (the `Manijero QA` window); between participants it resets the QA app by hand: remove each made-up land with `Quitar`, delete it in `Terrenos eliminados` with `Borrar para siempre`, and show the welcome card again with `Ayuda` → `Ver bienvenida`. After each participant it runs `./scripts/init.sh --usability-record`. It never asks anyone to type real names, places, or land data.

### 5. Recording one participant

Given no results file yet · When the owner runs `./scripts/init.sh --usability-record` and answers the prompts (code `P1`; for each task a result `1` completed / `2` needed help / `3` gave up, whole minutes 0-60, an optional note; for task 3 whether the app asked to choose a land; an optional debrief note) and types `yes` at the recap · Then the results file is created outside the checkout with mode `0600`, it prints per-task counts and median minutes for all saved participants, and ends `Result: P1 was saved; the results file holds 1 participant: <path>.`, exit `0`. A second run with `P2` adds to the same file and the summary covers both.

### 6. Personal data is refused, never echoed

Given any prompt · When the code is not `P1`-`P99` (a name, a number, `P0`) · Then it is refused with `Use the code from the sheet, like P1. Do not type names.` When a note holds a capitalised word outside the fixed app-word list, a name cue (`se llama`, `don`, `señora`...), an address cue (`calle`, `avenida`...), five or more digits in a row, or what `app.input_guardrails` treats as personal data (phone, email, DNI, NIE, NIF, IBAN) · Then it is refused with one fixed sentence asking to write it again without names or personal details (small letters except app words). The refused text is never printed, logged, or written. Three invalid answers in a row to one prompt stop the run with `Result: nothing was saved. Run ./scripts/init.sh --usability-record again.`, exit `1`.

### 7. Replacing, stopping, and bad files change nothing by surprise

Given `P1` is already saved · When the owner types `P1` · Then it says P1 is already saved and asks for `yes` to replace it; anything else ends with nothing changed, exit `1`. Given Ctrl+C, end of input, or no `yes` at the recap · Then nothing is written, the file is byte-identical, and the `Result:` line says nothing was saved, exit `1`. Given an unreadable or unexpected results file · Then it changes nothing and ends `Result: the results file could not be read, so nothing was saved. Send <path> to the developer.`, exit `1`. Given anything after the command · Then one sentence and exit `2`, with no prompt and no file written. Given a missing `backend/.venv` · Then the existing "not set up yet" pair, exit `1`.

### 8. Owner guide walkthrough

Given `docs/owner-guide.md` · Then it has a section titled exactly `Owner walkthrough: usability session` with numbered steps (prepare QA and the app, print the kit, run each participant, record, reset, send the summary), the expected `Result:` lines, one missing-prerequisite case (QA not running), one recovery (replace a mistyped participant), and a table of only the messages the owner can reach; at most about 60 lines.

## Technical approach

- **Kit.** Five Markdown files under `docs/usability-session/` (printable, short): `guion-facilitador.md`, `nota-consentimiento.md`, `tareas.md`, `hoja-observacion.md`, `preguntas-finales.md`. Fixed made-up land cards, the task 3 question, timings, and debrief questions are in the appendix. Spanish copy follows [`DESIGN.md`](../../DESIGN.md) tone (plain, forgiving); quoted app labels are pinned by a test against `strings.xml`.
- **Command.** `scripts/init.sh` adds `--usability-record` to the early owner-command dispatch (same one-argument misuse check and "not set up yet" pair as `--demo-rehearsal`), then `exec`s `backend/scripts/usability_record.py`. Update `usage` and the `--check` listing. Prompts and output are English, like every other owner command; outcome prompts also show the Spanish sheet labels.
- **Recorder.** Logic in a new operator-only `backend/app/usability_results.py` (never imported by the service): code validation, note screening, record model, atomic store, summary. The CLI reads answers through an injected prompter (follow `qa_deployment._confirm` / the `local_rag_bootstrap` prompter, where end of input is `None`). Personal-data patterns reuse `app.input_guardrails.screen_question(text) == "personal_data"`; the name, cue-word, address, and digit-run rules are local constants. Notes at most 200 characters, debrief note at most 400.
- **Results file.** `~/manijero/usability/usability-results.json` (folder `0700`, file `0600`, written via temp file + rename), schema `usability-results-v1`: `participants` sorted by code, each with four task records (`task` id, `outcome` in `completed|needed_help|gave_up`, `minutes`, `note`), `land_choice_shown` on task 3, and `debrief_note`. No dates, times of day, names, or free fields beyond the screened notes. `MANIJERO_USABILITY_HOME` overrides the folder for tests only and is refused inside the checkout. `.gitignore` gains a `usability-results*.json` guard against an accidental copy.
- **Exits.** `0` saved; `1` stopped, declined, refused three times, or unreadable file; `2` misuse. No tracebacks; an unexpected error prints a plain line and `Result:`.
- Follow [`docs/constraints/operations.md`](../constraints/operations.md) for the one-command, confirmation, and `Result:` rules, and [`rag_demo_rehearsal.md`](rag_demo_rehearsal.md) for the dispatch and owner-guide shape.

## Expected file changes

- `docs/usability-session/guion-facilitador.md`, `nota-consentimiento.md`, `tareas.md`, `hoja-observacion.md`, `preguntas-finales.md` — create.
- `backend/app/usability_results.py`, `backend/scripts/usability_record.py` — create.
- `backend/tests/test_usability_session.py` — create: kit guards, recorder, refusals, file safety, `init.sh` dispatch/misuse.
- `scripts/init.sh` — modify: dispatch, `usage`, `--check` listing. `.gitignore` — modify: one guard line.
- `docs/owner-guide.md`, `backend/README.md`, `ARCHITECTURE.md`, `docs/constraints/operations.md` — modify (see below).
- Not changed: `shared/`, `androidApp/`, `desktopApp/`, Gradle files, `contracts/`, `knowledge/`, `backend/app/input_guardrails.py` (imported only), QA and service modules, `DESIGN.md`.

## Visual design impact

UI involved: no app change. The kit only quotes existing labels (`Antes de empezar`, `Entendido`, `Mis terrenos`, `Añadir terreno`, `Nombre del terreno`, `Zona o paraje`, `Guardar terreno`, `Elige el terreno de tu pregunta`, `Tiene en cuenta todos tus terrenos.`, `Fuentes`, `Publica:`, `Abrir documento oficial`, `Quitar`, `Terrenos eliminados`, `Borrar para siempre`, `Ayuda`, `Ver bienvenida`). No string, screen, or baseline changes.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one line: operator-only `usability_results.py`/`usability_record.py` behind `--usability-record`, writing anonymous results outside the checkout; never imported by the service.
- `docs/constraints/operations.md`: update — one MUST: a results-recording command stores only anonymous `P<n>` codes, fixed outcome codes, minutes, and screened notes outside the checkout with mode `0600`, refuses personal-data-looking input without echoing it, and asks before replacing a record. Reason: `usability_session`.
- `docs/owner-guide.md`: update — `Owner walkthrough: usability session` (scenario 8). `backend/README.md`: update — at most 30 lines (command, schema, screening rules and their limits, test-only variable).
- `AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, `contracts/`, `knowledge/README.md`: not needed — no workflow, glossary, UI, or contract change.
- At `passing`: one line each in `PROGRESS.md` and `docs/progress/known-limitations.md` (kit ready, no session run, lexical screening). At `accepted` (after the real session): `docs/risks-and-open-questions.md` usability row updated with the observed evidence, `docs/progress/session-log.md` line, follow-up items added.

## Focused verification (required)

Offline: no QA, service, app, or network; every recorder run uses a temporary `MANIJERO_USABILITY_HOME` and piped input.

<!-- verify:start -->
```sh
bash -n scripts/init.sh
MANIJERO_PYTHON="${MANIJERO_PYTHON:-backend/.venv/bin/python}" ./scripts/init.sh --backend-tests tests/test_usability_session.py -q
```
<!-- verify:end -->

The real session (Desktop QA app, 2-3 participants, `--usability-record`) is the owner walkthrough in `docs/owner-guide.md`; it is not part of this block and gates `accepted` (Notes 7).

## Appendix

See [`usability_session.appendix.md`](usability_session.appendix.md) for repository research, fixed kit values, plan, evidence, and the validator checklist.
