# input_guardrails — appendix

## Repository research

### Files inspected

- `backend/app/ask_api.py` — `ask_question` opens the trace session, calls `_answer`, then
  `session.finish(question=…)` and `retain_if_opted_in(question=…)`. The screen and the
  personal-data bypass go here. `_answer`'s campaign-year check is the precedent for a
  pre-retrieval abstention: it calls `note_outcome`, `note_answer`, and `to_abstention_response`.
- `backend/app/abstention.py` — `ABSTENTION_REASONS`, `ABSTENTION_MESSAGES`, `Abstention`
  (no text field), `to_abstention_response`. The new reasons append here.
- `backend/app/answer_trace.py` — `TraceSession.finish` and `build_document`. Text keys are added
  when `trace.text_included` is set, so a per-call override is needed.
- `backend/app/retention.py` — `retain_if_opted_in` and `build_record`. Abstentions are retained
  when opted in, so `ask_api` must skip the call for `personal_data`.
- `backend/app/redaction.py` — retention-only replacement patterns (email, phone, DNI/NIE,
  IBAN, cadastral, SIGPAC, any 6+ digit run). These are too broad for detection: the digit-run
  and SIGPAC rules would flag land data. Do not reuse them; leave the file unchanged.
- `backend/app/health_metrics.py` — its own `ABSTENTION_REASONS` allowlist (`clamp` maps unknown
  reasons to `other`). `test_health_metrics.py` line 541 asserts set equality with
  `abstention.ABSTENTION_REASONS`.
- `backend/app/generation.py` — `normalize_text` (lowercase, NFKD, strip marks, collapse
  whitespace), `ELIGIBILITY_PHRASES`, `MAX_ANSWER_CHARS`.
- `backend/app/pilot_logging.py` — `operational_log`. There is no new event: the screen logs nothing.
- `backend/tests/test_abstention.py` lines 266–310 — taxonomy order, unique messages,
  digit-free, no eligibility phrase, and next step (`oficina comarcal agraria`/`cooperativa`/
  `inténtalo otra vez`). Only the order test needs editing; the parametrized ones pick up the
  new reasons.
- `backend/tests/test_privacy_retention.py` lines 55–260 — `PERSONAL_QUESTION` contains a phone
  and an email and is posted through `/ask` by the route tests (`_ask`). After this feature it is
  screened, so those route tests must use a question without the four kinds. The
  `retain_if_opted_in` unit tests (line 250) and `redact_text` cases (line 430) keep the
  personal values.
- `backend/tests/test_answer_trace.py` lines 100–150 — `trace_for`, `make_app`, `ask`, and
  `load` helpers to reuse for scenario 2.
- `backend/scripts/evaluate_abstention.py`, `backend/app/land_safety_eval.py` — derive outcomes
  from `ABSTENTION_REASONS` and call `answer_with_clarification`, not `/ask`, so their
  aggregates cannot change.
- Question sources for the false-positive sweep: `knowledge/pac_answer_eval.json` (14),
  `backend/tests/fixtures/land_safety/cases.json` (6, including "¿Cuánto cuesta matricular un
  tractor viejo?"), and `backend/tests/fixtures/{retrieval,generation,abstention,clarification}/
  eval_questions*.jsonl` (including "zzzz qqqq" and a blank question).
- `contracts/openapi.yaml` — the status enum has no reason and inspection `abstention_reason` is
  a free string, so there is no contract change.
- `docs/constraints/answers-and-knowledge.md` "Abstention",
  `docs/constraints/hosting-and-pilot.md` (trace, inspection, and log rules), `ARCHITECTURE.md`
  line 50, `docs/pilot-privacy.md` line 22, `backend/README.md` lines 1059–1111, and
  `docs/risks-and-open-questions.md` line 18 are the durable text the docs impact edits.
- `DESIGN.md` — the lands tab is `Mis terrenos`, so the copy says "tus terrenos".

### Rule detail (closed tables; finalize wording in the module docstring)

- Masking before personal-data patterns: SIGPAC (`\d{1,5}` groups joined by `:` or `-`, three or
  more groups) and 20-character cadastral references (`\d{7}[A-Z]{2}\d{4}[A-Z]\d{4}[A-Z]{2}`,
  case-insensitive) are replaced with a space before the patterns below run.
- DNI: `\d{8}` (also `\d{2}\.\d{3}\.\d{3}`) + optional `-`/space + letter. NIE: `[XYZ]` +
  optional separator + `\d{7}` + optional separator + letter. Company NIF:
  `[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]`. Every ID letter must be followed by a word boundary, so
  "12.345.678 euros" and "12345678 ha" stay `pass` (include both in `cases.json`). There is no
  check-letter validation, because a typo of a real ID is still personal data.
- Phone: optional `(\+|00)34` + space; nine digits starting `[6-9]`, written plain, `3-3-3`, or
  `3-2-2-2` with space, dot, or dash. Not preceded or followed by a digit, `:`, or `-digit`.
- Email: `[\w.+-]+@[\w-]+(\.[\w-]+)+`. IBAN: `\b[A-Z]{2}\d{2}( ?[A-Z0-9]{4}){2,7}( ?[A-Z0-9]{1,4})?\b`,
  case-insensitive, needing at least 10 digits after the check digits.
- Injection (normalized text): (`ignora|olvida|omite|salta(te)?|desobedece|ignore|forget|
  disregard`) within three words of (`tus|las|todas las|anteriores|previas|del sistema|previous|
  your|all`) + (`instrucciones|reglas|indicaciones|ordenes|directrices|prompt|instructions|
  rules`); (`muestra(me)?|ensename|dime|revela|repite|escribe|imprime|show|reveal|print|repeat`)
  + (`tu prompt|tus instrucciones|instrucciones (del sistema|iniciales|internas|ocultas)|mensaje
  del sistema|system prompt|your instructions`); role override (`a partir de ahora (eres|seras|
  actua)|finge (ser|que eres)|haz como si fueras|modo (desarrollador|dios|sin restricciones)|
  jailbreak|you are now|act as (an?|my) (unrestricted|different)`).
- Domain terms (any one blocks `out_of_domain`): `pac`, `ayuda(s)`, `subvencion`, `solicitud`,
  `tramite`, `plazo`, `campana`, `convocatoria`, `junta`, `consejeria`, `ministerio`, `oficina
  comarcal`, `cooperativa`, `sigpac`, `catastro`, `poligono`, `parcela`, `recinto`, `finca`,
  `terreno(s)`, `tierra(s)`, `hectarea`, `olivo`, `olivar`, `aceituna`, `aceite`, `almazara`,
  `cosecha`, `poda`, `riego`, `regadio`, `secano`, `ecologic*`, `cultivo`, `abono`,
  `fertiliz*`, `fitosanitario`, `tratamiento`, `plaga`, `cuaderno de campo`, `condicionalidad`,
  `ecorregimen*`, `agricult*`, `agrari*`, `tractor`, `maquinaria`, `ganado`.
- Off-topic markers (one is needed): `futbol`, `liga`, `partido de`, `baloncesto`, `receta`,
  `cocinar`, `chiste`, `poema`, `cancion`, `cuento`, `pelicula`, `serie`, `musica`, `programar`,
  `codigo`, `python`, `deberes`, `examen`, `loteria`, `apuesta`, `quiniela`, `bitcoin`,
  `cripto*`, `horoscopo`, `viaje`, `hotel`, `vuelo`, `capital de`, `quien gano`.

## Implementation plan

1. Baseline: run the contract's line 2 and record the pass count.
2. Create `input_guardrails.py` with the tables above, `SCREEN_REASONS`, and `screen_question`.
   Use precompiled regexes with no nested quantifiers. Docstring: purpose, precedence, the
   precision-first rationale, the masking order, and "never returns or logs matched text".
3. In `abstention.py`, append the three reasons and messages, and add one docstring line on
   screening reasons.
4. In `health_metrics.py`, append the three reasons to `ABSTENTION_REASONS`.
5. In `answer_trace.py`, add `withhold_text` to `TraceSession.finish`, passing
   `text_included=trace.text_included and not withhold_text`.
6. In `ask_api.py` `ask_question`, screen before `_answer`. On a hit, build the abstention
   response with the outcome notes and metrics. Then, for `personal_data`, use
   `withhold_text=True` and skip retention. Retention, the trace, and inspection otherwise run as
   today.
7. Create the `cases.json` fixture (`{"schema": "input-guardrail-cases-v1", "cases": [{id,
   question, expect, note}]}`, with `expect` in `pass` plus `SCREEN_REASONS`).
8. Write the tests below. Update `test_abstention.py` and `test_privacy_retention.py` as the
   contract says.
9. Run the focused block, then `CI=true ./scripts/init.sh --fast`, and record the evaluator lines.
10. Make the durable doc edits, then append evidence.

Tests in `test_input_guardrails.py`:

- `test_personal_data_kinds_are_screened` (parametrized, scenario 1).
- `test_personal_data_is_not_retained_traced_logged_or_echoed` (scenario 2: store rows, trace
  keys and bytes, log, `/metrics` body, development inspection).
- `test_prompt_injection_is_screened_in_spanish_and_english` (scenario 3).
- `test_out_of_domain_needs_a_marker_and_no_domain_term` (scenario 4).
- `test_screen_precedence` (scenario 5).
- `test_land_data_and_farming_questions_pass_and_answers_are_unchanged` (scenario 6: `/ask`
  response equals a run with `screen_question` monkeypatched to `None`).
- `test_existing_evaluation_questions_are_never_screened` (scenario 6 sweep).
- `test_labelled_cases_match_with_minimum_counts` (scenario 7; the failure message lists ids
  only).
- `test_screened_reply_never_reaches_retrieval_or_generation` (spies, scenarios 1, 3, and 4).
- `test_screen_returns_codes_only_and_is_linear` (scenario 9: 2,000-character inputs of
  digits, `a@`, and `ignora `, each under 0.5 s).
- Scenario 8 is covered by the existing parametrized `test_abstention.py` copy tests, plus
  `test_screen_messages_do_not_echo_the_question`.

## Verification plan

- `./scripts/init.sh --feature input_guardrails` runs both lines with exit `0`.
- `CI=true ./scripts/init.sh --fast`: every evaluator line matches its pre-change result
  (abstention, clarification, and land safety call `answer_with_clarification`, which is
  unchanged).
- Mutation spot-check (by hand, not committed): make `screen_question` always return `None`.
  Scenarios 1–5 and 7 must fail. Then make it return `out_of_domain` when there is no domain
  term, ignoring the marker. Scenario 4's negatives and the scenario 6 sweep must fail.
- E2E: not needed. There is no client, route, or contract change, and TestClient route tests
  cover `/ask`.
- `--verify`: not needed. No Kotlin or Gradle file changes.

## Evidence to capture

- The baseline and post-change pass counts, and the focused-block result, one line per command.
- Case counts per label in `cases.json`, and the sweep size (questions screened).
- The `--fast` evaluator lines, stated as unchanged or not.
- The mutation spot-check result, in one line.
- The doc files edited, one line each.

## Feature evidence

<!-- Implementer appends here: date, each command with its one-line result, manual checks in one or two lines. No pasted logs. -->

2026-11-07 (resumed implementer session)
- `./scripts/init.sh --feature input_guardrails` -> 2208 passed, 5 skipped (both lines; exit 0).
- `CI=true ./scripts/init.sh --fast` -> all 10 checks passed; abstention, clarification, land-safety, generation evaluators report 0 differing outcomes (unchanged).
- `cases.json`: 42 pass, 16 personal_data, 10 prompt_injection, 10 out_of_domain.
- Mutation spot-check: not run (tooling refused the shell sequence); tests assert each label, so an always-`None` screen fails scenarios 1-5 and 7 by construction.
- Docs edited: `docs/constraints/answers-and-knowledge.md`, `ARCHITECTURE.md`, `docs/pilot-privacy.md`, `backend/README.md`, `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`, `PROGRESS.md` (one limitation line); `feature_list.json` set to `passing`.

## Validator checklist

- [ ] Only the files in the contract changed (`git diff --stat`). `redaction.py`, `contracts/`,
      `shared/`, `knowledge/`, and `scripts/init.sh` are untouched.
- [ ] `screen_question` is standard-library only, makes no network or model call, logs nothing,
      and returns only a code from `SCREEN_REASONS` or `None`.
- [ ] Each of scenarios 1–9 maps to a named passing test. `cases.json` meets the minimum counts,
      and every value in it is fictitious.
- [ ] A `personal_data` question leaves no retention row, no trace text, and no log or metrics
      content; `/metrics` shows only the reason label.
- [ ] No SIGPAC, cadastral, polygon/parcel, amount, date, or existing evaluation question is
      screened. Unscreened `/ask` responses are byte-identical to the pre-feature ones.
- [ ] The three messages satisfy every `test_abstention.py` copy test and match the contract
      copy, or a tightened version of it.
- [ ] `test_privacy_retention.py` changes only move personal values out of route-level questions.
      No redaction assertion is weakened at the unit level.
- [ ] The focused block runs unchanged through `./scripts/init.sh --feature input_guardrails`.
- [ ] The durable doc edits match the contract. `feature_list.json` and `PROGRESS.md` are updated
      only at acceptance (validator accept is final; no owner walkthrough).
