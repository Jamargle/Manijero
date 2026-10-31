# Feature Spec: `coverage_and_help`

## Source metadata

- **Feature:** `coverage_and_help` — Coverage limits and human help (`client`)
- **Status at planning:** `not_started`. This feature did **not** exist in `feature_list.json`; it is
  now registered in the lean feature index. It is the unimplemented WBS task **D10
  ("Coverage and Help — declare content limits and human referral paths")** and MVP screen
  **§17.1 #7** of `docs/archive/MasterPlanV3.md`, backed by closed decision **D12** ("the app must not imply
  unsupported topics are covered") and §17.4 limit behavior.
- **Source behavior:** A person can see, in plain Spanish, what questions the assistant is built to
  answer and what it will not answer, and where to get human help — without asking a question first
  and without being promised coverage the corpus does not have.
- **Feature-list verification:** Open the coverage screen on Android and Desktop and read, in one
  place: the covered topic areas, the explicitly-not-answered cases, and the human referral paths;
  confirm nothing on the screen promises an answer for an uncovered topic.
- **Feature-list note:** The covered-topic list is pinned copy that must track the actual reviewed
  corpus scope (`reviewed_seed_corpus`); it is a disclosure, not a live catalog query, and never a
  legal statement.
- **Handoffs received:**
  - `land_data_disclosure` non-goal: "No blocking first-use gate … that belongs to a separate
    welcome/first-use slice (`CR1`)" and its `privacy_help_body` ("habla con tu oficina comarcal
    agraria o con tu cooperativa") — the existing human-help paragraph this feature must not
    contradict; the welcome/first-use slice stays **out** of this feature.
  - `safe_abstention` / `ask_route`: the refusal classes (out-of-corpus, cooperative practices,
    personalized amounts, eligibility, unsafe requests) define what the "no responde" copy may
    claim; the copy must not enumerate abstention reason codes or promise a specific message.
  - `reviewed_seed_corpus` (planned alongside): the seeded topic areas (PAC solicitud única and its
    presentation/modification deadlines, SIGPAC basics, olive-aid requirements and active-farmer/
    surface rules, Andalusian single-application procedure, notifications/rectifications basics) and
    the explicitly uncovered ones (organic production, irrigation/water, conditionality specifics,
    the digital notebook, agricultural insurance, pruning-waste burning, Junta aid beyond the seeded
    calls, personalized amounts and eligibility).
  - `DESIGN.md` MVP surface 7 ("Privacy/help … Link to human help for questions the app cannot
    answer") and `docs/domain-model.md` / `docs/archive/build-brief.md` plain-Spanish accessibility rules.
  - `chat_accessibility` / `land_form_accessibility`: the accessibility baseline and evidence rules
    (large text, screen-reader labels, no colour-only meaning) this screen must follow.
- **Size:** one stateless shared screen, one pinned Compose-free content module, one navigation
  destination, one labelled chat-home control, a link from the existing privacy screen, strings,
  previews, and pure tests. One user flow, no new data model, no backend or contract change.

## Goal and boundaries

Answer the question "¿hasta dónde llega esto?" before the person relies on the assistant. Today the
app explains privacy/help (`PrivacyScreen`) but never states its **coverage limits**: a person can
easily assume the assistant knows everything about grants and paperwork. This slice adds a calm,
plain-Spanish coverage disclosure — what it is built to answer, what it deliberately will not answer
(cooperative practices, personalized amounts, "am I eligible"), and where a human answers instead —
reachable from the chat home, in the style of the accepted privacy notice.

**In scope**

- A pinned, Compose-free content module (`coverage/CoverageContent.kt`) holding the reviewed
  structure of the disclosure: covered topic areas, not-answered cases with a one-line reason, and
  the human referral paths (oficina comarcal agraria, cooperativa) — named, never invented contact
  details.
- A stateless `CoverageScreen` in `commonMain` rendering that content in plain Spanish: short
  sentences, no legal jargon, sections with headings, scrollable, theme-only styling.
- Navigation: `AppDestination.Coverage` in `App()`, opened from a labelled chat-home control
  (alongside `Privacidad y ayuda`), with `Volver` returning to the previous destination; a cross-link
  from `PrivacyScreen`'s help section to the coverage screen and back.
- Copy shipped verbatim in `strings.xml` (new keys only; no accepted string changes) and previews
  inside `ManijeroTheme` (default, narrow/large-text variant).
- Pure `commonTest` coverage pinning the content structure (every section present; no section
  asserting a legal conclusion) and the covered-topic list's correspondence with the corpus scope.

**Non-goals**

- No welcome/first-use gate or "notice seen" state (that is the separate `CR1` slice; this screen is
  reachable, not blocking).
- No feedback collection, ratings, contact forms, question logs, or analytics (`docs/archive/MasterPlanV3.md`
  D9 feedback stays optional and separate).
- No live query of `knowledge/` or the backend: the disclosure is pinned copy (the app works
  offline of the corpus), with a durable rule that it must be updated when corpus scope changes.
- No phone numbers, email addresses, opening hours, appointment or fee information for any
  cooperative or office (MasterPlan §17.4: cooperative specifics are never answered) — referral is
  by name and role only.
- No change to abstention copy, the failure notice, the legal-notice lines owned by
  `grounded_answer_generation`, the privacy notice's existing sections, or any accepted chat/land
  behavior.
- No new module, dependency, navigation framework, ViewModel, coroutine, or logging; no legal advice,
  eligibility claim, deadline, amount, or article number in the copy.

## Job story

When I am about to rely on this assistant for a subsidy or paperwork question, I want to know in
plain words what it can actually help with and what it will not touch — and who to ask instead — so
I do not waste time or act on something outside its knowledge.

## Acceptance scenarios

### The limits are visible without asking a question

Given the chat home is open, when the person looks at it, then a labelled control for the coverage
screen is visible next to the accepted `Privacidad y ayuda` control (no question, no land setup
required), and activating it opens the coverage screen with its three sections: what the assistant
is built to answer, what it will not answer, and where to get human help.

### Covered means "built to answer", never "will answer"

Given the covered-topic section, then it names topic areas (for example: plazos de la solicitud
única, qué es el SIGPAC, requisitos de las ayudas del olivar) in plain Spanish and each line is
phrased as a topic, not a promise or a legal conclusion. Given any text on the screen, then it
contains no deadline, amount, threshold, article number, or "te corresponde"-style eligibility
claim, and no word like "garantizado", "seguro", or "correcto" about answers.

### What is not answered is explicit

Given the not-answered section, then it names the refusal classes the product actually enforces:
prácticas concretas de tu cooperativa (horarios, citas, precios), cuánto cobrarías o si te
corresponde una ayuda, temas que todavía no están en sus documentos oficiales, and anything outside
olive-grove bureaucracy — each with a one-line plain-Spanish reason and no abstention reason code or
server wording. Given the corpus scope of the implemented `reviewed_seed_corpus`, then topics it
does not cover (producción ecológica, riego/agua, condicionalidad en detalle, cuaderno digital,
seguros agrarios, quema de restos de poda) appear here as "todavía no".

### Human help is a named path, not invented detail

Given the help section, then it repeats the accepted referral in the same spirit as
`privacy_help_body` (tu oficina comarcal agraria o tu cooperativa) and explains in one sentence what
to ask there (plazos internos de la cooperativa, dudas personales sobre tu expediente). Given the
screen's link affordances, then they navigate only within the app (to the privacy screen and back);
no external link, phone number, or address is shown or invented.

### Accessible and consistent

Given the screen at `fontScale = 2.0` and on a narrow Desktop window, then nothing is clipped, the
content scrolls, headings and sections are announced coherently (merged semantics where
appropriate), no meaning is carried by colour alone, and the `Volver` control is reachable by
keyboard with visible focus on Desktop. Given any rendering, then it uses only the accepted
`ManijeroTheme` tokens and the accepted 720dp content width treatment.

### Nothing else changes

Given the coverage screen exists, then every accepted string, reducer, request payload, and
rendering is byte-unchanged; the privacy screen's existing sections are unchanged apart from the one
cross-link; `contracts/`, `backend/`, `knowledge/`, `init.sh`, and the platform entry points are
untouched.

## Repository research and planning record

Inspected (2026-10-16):

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` —
  `private enum class AppDestination { Chat, LandList, AddLand, EditLand, RemoveLand, Privacy }`;
  `Chat` renders `ChatHomeScreen(..., onPrivacyClick = { destination = AppDestination.Privacy })`,
  and `PrivacyScreen(onBack = { destination = AppDestination.Chat })`. Adding a `Coverage`
  destination follows the exact accepted pattern (no navigation framework).
- `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt` and
  `privacy/LandDataDisclosure.kt` — the accepted template: a pinned, Compose-free content module plus
  a stateless screen rendering it, with `privacy_help_title` / `privacy_help_body` ("Para dudas sobre
  ayudas o trámites que la app no pueda responder, habla con tu oficina comarcal agraria o con tu
  cooperativa.") and `privacy_back` ("Volver").
- `shared/src/commonMain/composeResources/values/strings.xml` — all user-facing copy is
  resource-backed; the privacy block (lines ~81-103) is the style reference; `chat_home_privacy`
  ("Privacidad y ayuda") is the chat-home control label to sit beside.
- `docs/specs/land_data_disclosure.md` — structure to mirror (Source metadata → Validator checklist),
  its non-goal naming `CR1` as the welcome/first-use slice, and its "copy contract" approach
  (strings ship verbatim; a pure test ties copy to the real payload).
- `docs/specs/chat_accessibility.md`, `land_form_accessibility.md`, `DESIGN.md` "Accessibility and
  validation" + "MVP surfaces" (surface 7 = Privacy/help) — the accessibility baseline, the rule
  that accessibility is not claimed without performed checks, and the no-UI-test-harness limit that
  forces preview/manual evidence.
- `docs/specs/answer_source_cards.md` — the 720dp capped/centred column convention and the
  merged-semantics card pattern.
- `docs/archive/MasterPlanV3.md` §7.3 (procedure map topics), §11.2 (seed-corpus coverage), §12.4 (trap classes
  the assistant must refuse), §17.1 #7, §17.4 (limit behavior), D12 (declared coverage).
- `CONSTRAINTS.md` sections "Client response states", "Land data disclosure", "Chat accessibility",
  "Land form accessibility" — the MUST rules the new screen must respect.

Not inspected: `shared/build.gradle.kts` resource wiring details (already exercised by accepted
features), the iOS target files (untouched), and any localization beyond `values/strings.xml`
(the app ships Spanish only).

## Technical approach

1. **Pinned content module** (`coverage/CoverageContent.kt`, Compose-free), mirroring
   `LandDataDisclosure.kt`: a small structure of section descriptors (covered topics as a list of
   plain-Spanish topic lines; not-answered cases as case + one-line reason; help paths as name +
   one-line what-to-ask), each resolving to string resource keys. Pure tests assert: every section
   exists, every topic line is non-blank, no entry contains a digit sequence that could read as a
   date/amount (cheap guard against accidental legal facts), and the covered-topic list equals the
   pinned corpus-scope list (so a corpus change without a copy change fails the suite).
2. **Screen** (`coverage/CoverageScreen.kt`), stateless like `PrivacyScreen`: title, short intro,
   the three sections as readable blocks, one `Volver` control; accepted theme tokens only
   (`surface`, `outlineVariant`, `surfaceVariant`/`onSurfaceVariant` for secondary text,
   `primary` for the control), no raw colours, no badge implying confidence. Sections use merged
   semantics nodes for screen-reader coherence (the `answer_source_cards` card pattern).
3. **Wiring in `App()`**: `AppDestination.Coverage`; a labelled chat-home control
   (`coverage_open`, e.g. "Qué cubre la app") rendered beside `onPrivacyClick`;
   `CoverageScreen(onBack = …)` restores the previous destination (chat or privacy, whichever opened
   it — a tiny `previousDestination` value or separate callbacks, matching the existing simple enum
   state; no back-stack library). `PrivacyScreen` gains one cross-link control to the coverage
   screen (new string; existing strings unchanged).
4. **Copy contract**: all new copy ships verbatim in `strings.xml` (new keys only), plain Spanish,
   short sentences, no jargon without explanation, `usted`-free informal style consistent with the
   existing notice. Phrasing rules: "está preparado para responder sobre…" not "resuelve…";
   "todavía no" not "no sirve"; never "garantiza", "comprueba", "te corresponde".
5. **Corpus-scope correspondence**: the pinned covered-topic list must name exactly the topic areas
   `reviewed_seed_corpus` actually seeded (its document set: solicitud única y plazos, SIGPAC, ayudas
   del olivar/agricultor activo/superficies, procedimiento andaluz de solicitud, notificaciones
   básicas). If the corpus scope changes, the copy and this list must change in the same review —
   recorded as a CONSTRAINTS rule and checked by the pure test's pinned expectation.
6. **Accessibility evidence** follows the accepted approach (no Compose UI-test harness):
   previews at default + large text + narrow width, manual Android/Desktop checks recorded
   (fontScale 2.0, uiautomator/AX dump, keyboard pass), and no accessibility claim beyond what was
   performed.

## Expected file changes

| File | Change | Why |
|---|---|---|
| `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageContent.kt` | **Create** | Pinned, Compose-free disclosure structure. |
| `shared/src/commonMain/kotlin/com/jamarglex/manijero/coverage/CoverageScreen.kt` | **Create** | Stateless screen + previews inside `ManijeroTheme`. |
| `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt` | **Update** | `AppDestination.Coverage`, chat-home control, back routing, privacy-screen cross-link target. |
| `shared/src/commonMain/kotlin/com/jamarglex/manijero/privacy/PrivacyScreen.kt` | **Update** | One cross-link control in the help section (existing copy unchanged). |
| `shared/src/commonMain/composeResources/values/strings.xml` | **Update** | New keys only (screen title/intro/sections, chat-home control label, cross-link, `Volver` reuse). |
| `shared/src/commonTest/kotlin/com/jamarglex/manijero/coverage/CoverageContentTest.kt` | **Create** | Pure tests pinning structure, no-legal-fact guard, and corpus-scope correspondence. |
| `CONSTRAINTS.md` | **Update** | One "Coverage disclosure" MUST rule (below). |
| `DESIGN.md` | **Update** | Keep a concise coverage/help surface summary and link to this spec; place inspection evidence in the validation record, not the design guide. |
| `PROGRESS.md` | **Update** | Evidence (after implementation verification only). |

Not touched: `contracts/`, `backend/`, `knowledge/`, `init.sh`, Gradle, platform entry points,
every accepted reducer/service/string (existing keys byte-unchanged).

## Visual design impact

One new surface in the accepted language: same page background and card treatment as `PrivacyScreen`,
same 720dp content-width convention as the chat surface (and the known `desktop_mvp_build` H1 finding
about uncapped land/privacy surfaces applies here too — this screen should use the capped/centred
treatment from the start), same typography roles (`titleLarge`/`titleMedium`/`bodyMedium`-family per
`DESIGN.md`), `primary` only on the `Volver` and cross-link controls. Caution/danger tokens are **not**
used: this is neutral information, not a warning. No illustration, badge, or confidence cue.

## Cross-feature interactions and handoffs

- **Depends on `reviewed_seed_corpus`** for the honest covered-topic list and on `land_data_disclosure`
  for the notice/help patterns and the `CR1` boundary.
- **To `safe_abstention` / `ask_route`:** the not-answered copy must stay consistent with the refusal
  classes those implement; if a new refusal class appears, the copy is revisited (CONSTRAINTS rule).
- **To the future welcome/first-use slice (`CR1`):** this screen is its natural content source;
  nothing here creates a gate or a seen-flag.
- **To `chat_accessibility`:** this screen's accessibility evidence is recorded in the same style;
  the carried low-digital-confidence manual session remains an outstanding check owned there.

## Implementation plan and tasks

1. Pin the covered/not-answered/help content against the actual `reviewed_seed_corpus` scope (read
   `knowledge/source_catalog.json` at implementation time; if the corpus is not merged yet, write
   the list from the spec's topic set and mark the correspondence test to the planned scope).
2. Add `CoverageContent.kt` + `CoverageContentTest.kt` (structure, no-legal-fact guard, scope
   correspondence) and make the tests pass.
3. Add `CoverageScreen.kt` with previews (default, large text, narrow) in `ManijeroTheme`.
4. Wire `AppDestination.Coverage`, the chat-home control, `Volver` routing, and the privacy-screen
   cross-link; keep every accepted string and behavior unchanged.
5. Ship the new `strings.xml` keys verbatim (new keys only).
6. Verify per the plan below; record accessibility evidence honestly (what was performed vs
   preview-only).
7. Update `CONSTRAINTS.md` and `DESIGN.md`; record evidence before touching `feature_list.json`
   status.

## Verification plan and evidence

<!-- verify:start -->
./gradlew :shared:jvmTest
python3 scripts/validate_coverage_copy.py
<!-- verify:end -->

- `./gradlew :shared:jvmTest` and `./gradlew :shared:testAndroidHostTest :androidApp:assembleDebug :desktopApp:build`,
  plus `./scripts/init.sh --verify` → green; no previously passing test regresses. (If the Android SDK is
  unavailable, record the exact blocker — repo convention.)
- Manual smoke on Android emulator and Desktop: from the chat home open the coverage screen without
  asking anything; read all three sections; follow the privacy cross-link and `Volver`; confirm the
  chat/land flows are unaffected.
- Accessibility checks actually performed and recorded (as `chat_accessibility` did): `fontScale`
  2.0 on the emulator (uiautomator dump: no clipping, coherent labels), narrow/wide Desktop window,
  keyboard traversal to and from the new controls, screen-reader announcement sanity; preview-based
  structural evidence for anything not performable — never claimed as inspected renders.
- Copy review by eye against the phrasing rules (no promise wording, no figures/dates/article
  numbers, no cooperative specifics) — a checklist line in the evidence, since this is a
  judgment-quality property.
- Evidence to capture: command outputs, screenshots/dumps per case, the copy checklist, and the diff
  limited to the file table. No E2E/UI automation claim (no harness exists).

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update** | One "Coverage disclosure" MUST rule: the coverage copy MUST name only topic areas the reviewed corpus covers, MUST state the not-answered classes (cooperative practices, personalized amounts/eligibility, out-of-corpus topics), MUST NOT contain a deadline, amount, threshold, article number, eligibility claim, or invented contact detail, and MUST be updated in the same change that widens or narrows corpus scope. |
| `DESIGN.md` | **Update** | Retain the concise coverage/help surface summary and spec link; do not duplicate feature-specific accessibility evidence or limitations. |
| `PROGRESS.md` | **Update** | Evidence (after verification only). |
| `AGENTS.md` | **Not needed** | Plain-Spanish and no-invented-legal-facts rules already exist. |
| `ARCHITECTURE.md` | **Not needed** | Does not exist; no architectural boundary changes. |
| `docs/archive/MasterPlanV3.md` | **Not needed** | This implements WBS D10 / §17.1 #7; the plan is context, not a status ledger. |

## Risks and open decisions

- **R1 Copy drifts from corpus scope** as documents are added later. Mitigation: the pinned
  correspondence test + the CONSTRAINTS same-change rule; the validator checks it.
- **R2 Coverage language over-promises** ("resuelve tus trámites"). Mitigation: the phrasing rules
  and the no-legal-fact test guard; validator reads every line.
- **R3 Two help surfaces confuse** (`Privacidad y ayuda` vs the coverage screen). Mitigation: the
  privacy screen cross-links here, the chat-home labels are distinct and plain, and both screens use
  the same visual language; revisit naming with the family usability session if needed.
- **R4 Scope creep toward feedback or a welcome gate** (MasterPlan lists both near this surface).
  Mitigation: explicit non-goals; they are separate features (`CR1`, feedback/D9).
- **Open:** the exact chat-home control label ("Qué cubre la app" vs "Qué puedo preguntar" vs
  "Cobertura y ayuda") — decide with the family's vocabulary during implementation, keeping it
  distinct from "Privacidad y ayuda"; and whether the covered list should eventually be generated
  from `knowledge/` (post-MVP tooling, not this slice).

## Validator checklist

- [ ] The coverage screen is reachable from the chat home with no question and no land setup, and `Volver`/cross-link navigation works on Android and Desktop.
- [ ] Covered lines are topic areas only; no line promises an answer; no deadline, amount, threshold, article number, or eligibility claim appears anywhere on the screen.
- [ ] The not-answered section names exactly the enforced refusal classes (cooperative specifics, personalized amounts/eligibility, out-of-corpus topics) without server reason codes.
- [ ] The help section names only oficina comarcal agraria / cooperativa with no invented contact detail, hours, or fees.
- [ ] Covered topics match the implemented `reviewed_seed_corpus` scope (correspondence test present and passing; no topic claimed that has no reviewed source).
- [ ] Large-text, narrow-window, keyboard, and screen-reader behavior is either evidenced or honestly marked preview-only; no unperformed accessibility claim.
- [ ] Existing strings, reducers, payloads, and rendering are byte-unchanged; `contracts/`, `backend/`, `knowledge/`, `init.sh`, and platform entry points untouched; diff matches the file table.
- [ ] `CONSTRAINTS.md` and `DESIGN.md` updated as specified; the copy review checklist is recorded in the evidence.

## Appendix

Repository research, implementation planning, verification, and validator checklist are retained in
this contract until implementation evidence is recorded. The evidence record belongs in
[`coverage_and_help.appendix.md`](../archive/specs/coverage_and_help.appendix.md), following the repository's feature
documentation convention. `docs/validations/coverage_and_help.md` will be the independent acceptance
record.
