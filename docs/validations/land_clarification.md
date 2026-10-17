# Validation — `land_clarification`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`land_clarification` implementation against `docs/specs/land_clarification.md`.

Feature id: `land_clarification`. Spec: `docs/specs/land_clarification.md`.
Claimed status: `passing` (self-verified by the implementer). Recommended state
update: the orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair the feature. It read the diff, re-ran
the acceptance checks, and independently reproduced the literal feature-list
verification with its own throwaway probes (created outside the repository, run,
and left outside it). No repository file was modified except this record.

## Review target

`git status --short` before and after validation:

- New (backend): `backend/app/clarification.py`,
  `backend/scripts/evaluate_clarification.py`, `backend/tests/test_clarification.py`,
  `backend/tests/fixtures/clarification/{catalog.json,passages.json,eval_questions.jsonl}`.
- New (docs): `docs/specs/land_clarification.md` (planner artifact).
- Modified (client, `commonMain`): `App.kt`, `ChatConversation.kt`,
  `ChatHomeState.kt`, `chat/LandContextBuilder.kt`,
  `composeResources/values/strings.xml`.
- Modified (tests): `ChatConversationTest.kt`, `ChatHomeStateTest.kt`,
  `chat/LandContextBuilderTest.kt`.
- Modified (docs): `CONSTRAINTS.md`, `backend/README.md`,
  `docs/specs/minimal_land_context.md`, `feature_list.json`, `PROGRESS.md`.

Untouched (verified per path with `git diff --stat`, empty output): `contracts/`,
`knowledge/`, `backend/app/{generation,retrieval,source_catalog,abstention}.py`,
`backend/app/main.py`, `backend/requirements.txt`, `theme/`, `lands/`, `androidApp/`,
`desktopApp/`, `iosApp/`, every Gradle/catalog file, and `scripts/init.sh`. `git diff --check`
clean.

## Checks actually run (reproduced, not trusted)

Environment: no `python` on `PATH`; pytest ran from a temporary venv outside the
repo (`/private/var/.../opencode/manijero-validator-venv`, Python 3.9.6) with the
repo's `requirements.txt` plus a venv-only `pytest`/`jsonschema`. **No repo
dependency was added** (`backend/requirements.txt` unchanged).

Backend / contract:

- `python3 contracts/validate_examples.py` → exit 0, "Validated 2 request and 3
  response examples"; `contracts/` byte-unchanged.
- `python3 -m py_compile` on the three new Python files → clean.
- `cd backend && python -m pytest tests/test_clarification.py -q` → **70 passed**.
- `cd backend && python -m pytest -q` → **469 passed** (399 existing + 70 new).
- Clarification CLI (catalog/passages/eval, `--as-of 2026-10-13 --k 5`) → exit 0;
  `corpus: current`, eligible sources 2, indexed passages 3; **5 answered, 1
  clarification with both ids `land-A, land-B`, 0 abstained, invariants hold, 0
  expect-mismatches**.
- Exit contract: two `--json` runs byte-identical (2326 bytes, `cmp` clean);
  `--fail-on-miss` exit 0 on the fixtures; an `answered`-expect mismatch exits 0
  without the flag and 1 with it (stdout identical); empty eval / `--k 0` exit 2;
  an expired catalog → `corpus: not_current`, `stale_evidence` for every question,
  `clarifications: 0`, exit 0.

Client (Gradle 9.8.0 wrapper):

- `./scripts/init.sh --verify` → BUILD SUCCESSFUL (exit 0).
- `./gradlew :shared:jvmTest --rerun-tasks` → BUILD SUCCESSFUL; **174 tests, 0
  failures, 0 errors, 0 skipped** (`ChatHomeStateTest` 38, `ChatConversationTest`
  15, `LandContextBuilderTest` 16).
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → **160 tests, 0 failures**.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → BUILD SUCCESSFUL.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` → BUILD
  SUCCESSFUL (72 tasks, 0 cache); debug APK produced (35,898,490 bytes).
- Greps: no `println/Log./Logger/printStackTrace/NSLog/System.out` in `shared/src`
  or `backend/app`; no `Color(0x` outside `theme/`; no `ViewModel`/lifecycle/DI
  import; `MinimalLandContext` still exactly the four contract properties.

Independent behavioral probes (synthetic corpus, not the implementer's tests):

1. Two lands differing on a restricted dimension → `NeedsLandClarification` with
   **both** ids, `answer == ""`, `sources == []`, `land_scope == "selected"` and
   exactly the five `AskResponse` keys.
2. Equal lands → `None` (delegates); equal-on-dimension with a restricting
   candidate still `None`.
3. `unknown`/omitted land attribute → `candidate_is_applicable` True, no
   clarification, no invented value.
4. `crop`-only applicability → never discriminates.
5. `selected` with two differing lands → `None` (loop protection);
   `general` → `None`; one land → `None`; no candidates → `None`.
6. Request order preserved and duplicate ids deduplicated (`("z","a")`).
7. `production_method` discriminates; `max_claims` window respected.
8. Every clarification payload validates against the dereferenced contract
   `AskResponse` (2020-12 `jsonschema`); extra-key and bad-enum negative controls
   rejected.

## Validator checklist outcome

- Two differing lands → `needs_land_clarification`, empty answer/sources,
  `land_scope: selected`, **both** ids: **PASS**.
- Non-differing lands / no restrictive candidate → accepted `all_active`
  answered/abstained path: **PASS** (byte-identical delegated payload).
- `unknown`/omitted never filters and invents nothing; `crop`-only never
  discriminates: **PASS**.
- `general` / one land / `selected` never clarify (no loops): **PASS**.
- Client resubmits exact original wording with `mode: selected` and only the
  chosen ids (needed attributes only), no second user message, chooser lists saved
  names from the local list, unknown ids ignored, never invented: **PASS**
  (`ChatConversationTest`/`ChatHomeStateTest`/`LandContextBuilderTest` + code
  read).
- Payload matches `AskResponse`; `contracts/validate_examples.py` passes with
  `contracts/` untouched: **PASS**.
- Do-not-touch files unchanged; synthetic labelled fixtures, no real legal fact:
  **PASS**.
- `commonMain` only; no new module/dependency/route/ViewModel/logging: **PASS**.
- Feasible checks pass with no regressions; honest limits declared: **PASS**.

## Findings

Non-blocking only.

- **N1 (evidence accuracy).** `feature_list.json`/`PROGRESS.md` record
  `:shared:jvmTest --rerun-tasks` as "174/0 (was 163; 11 new)". The measured
  baseline is **162** (matching the recorded `minimal_land_context` 162) and the
  three test files added **12** `@Test` cases (31→38, 13→15, 13→16), so the honest
  wording is "was 162; 12 new". The 174/0 result itself is reproduced. Fix the two
  numbers when persisting acceptance evidence.
- **N2 (UX detail).** The chooser derives its list from a `LaunchedEffect` read, so
  before the read resolves it briefly renders the no-lands fallback notice. Not
  incorrect (never fabricates a land) and structurally consistent with the spec's
  fallback requirement, but an inspected render should confirm the flicker is not
  confusing. Owner: `chat_accessibility`.
- **N3 (edge).** An over-128-char land id in a request would make
  `NeedsLandClarification.__post_init__` raise `ValueError` inside the CLI (uncaught
  → traceback, process exit 1) rather than a clean exit 2. The contract already
  bounds `land.id` to `maxLength: 128`, so a well-formed request cannot hit this; it
  is a defensive-hardening note, not a contract violation.
- **N4 (honest limits, carried).** No `/ask` route (`chat_question_submission` F1)
  and no Compose UI-test harness, so the backend decision is observed through the
  CLI/tests and the client flow through a fake `AnswerService` plus previews; no
  live end-to-end answer or automated UI coverage is claimed. Detection is lexical
  and conservative (can over-ask, never guesses); `land_safety_evaluation` owns
  measurement and `answer_land_scope` owns rendering the scope.

## Security assessment

Scoped to the feature and diff: no network/model call in the new module or CLI
(socket/guard unit tests; imports carry no `socket/urllib/httpx/requests`); no
logging of question, land, or payload content; no new route, auth surface, or
dependency; only opaque local land ids leave the device on a clarification, with
names/notes/area/timestamps staying client-side (verified by encoded-body
assertions); no invented legal fact in copy or fixtures (all labelled
synthetic/"no es una norma real"). No blocking security finding.

## Documentation / harness state

`CONSTRAINTS.md` gained the one land-clarification MUST rule; `backend/README.md`
documents the boundary, rules, CLI, and that `/health` stays the only route;
`docs/specs/minimal_land_context.md` carries the follow-up ownership note.
`scripts/init.sh` was **not** changed and `--verify` passes. `feature_list.json` and
`PROGRESS.md` report only commands actually run (aside from N1's count) and
honestly mark the feature self-verified, not accepted.

## Required follow-up

None blocking. On acceptance: correct the N1 baseline/added-test numbers in the
recorded evidence. N2–N4 are carried with their owners.
