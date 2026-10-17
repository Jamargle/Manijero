# Validation — `answer_source_cards`

## Verdict

**Accept** — 2026-10-13. Independent validation of the uncommitted
`answer_source_cards` implementation against `docs/specs/answer_source_cards.md`.

Feature id: `answer_source_cards`. Spec: `docs/specs/answer_source_cards.md`.
Claimed status: `passing` (self-verified by the implementer). State update: the
orchestrator sets `status` to `accepted` and records concise evidence.

The validator did not implement or repair the feature; it re-ran the acceptance
checks, read the diff, and independently reproduced the citation/marker behavior
with its own temporary probe test (created, run, and deleted before returning).
Two pre-existing files unrelated to this feature
(`lands/AddLandStateTest.kt`, `theme/ManijeroColorsTest.kt`) were temporarily
edited only to work around a repo-wide comma-in-test-name compile error for the
iOS test run, then restored byte-identical to HEAD.

## Review target

`git status --short` before and after validation showed exactly the expected
footprint (unchanged by validation):

- Modified (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`,
  `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`,
  `shared/src/commonMain/composeResources/values/strings.xml`.
- New (product): `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/CitationPresentation.kt`.
- Modified (tests): `ChatHomeStateTest.kt`, `ChatConversationTest.kt`.
- New (tests): `shared/src/commonTest/kotlin/com/jamarglex/manijero/chat/CitationPresentationTest.kt`.
- Modified (docs): `CONSTRAINTS.md`, `docs/specs/response_states.md`.
- New (docs): `docs/specs/answer_source_cards.md` (planner artifact).

Untouched: `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`,
`androidApp/`, `desktopApp/`, `shared/src/iosMain/`, every Gradle file and the
version catalog, `scripts/init.sh`, and the Android/Desktop entry points. `git diff
--check` clean. No new module, dependency, endpoint, permission, ViewModel, DI,
navigation, engine, or shipped fake; no logging.

Validated product artifact hashes (sha256):

- `App.kt` `5f71eec3bb758e8598b0209dc426a00a49ae5c482bc5e650fcc26b31a0027ac7`
- `ChatHomeState.kt` `fc50d350cc3dbad25849e4d8c489183758d6b86f8ff57b48ff064a7e153c194e`
- `chat/CitationPresentation.kt` `9ae264dd3d8fc1953533710eb86e7bc2258480faeace03d1d00f34a22959b6ce`
- `strings.xml` `fe2e9b2240863a30a3adcca5e1bf5a61fa24dd46f524cb486e3010c4c6bbf96a`

## Independent checks and results

Re-run by the validator (with `--rerun-tasks` where relevant) so results are real
executions, not cached `UP-TO-DATE` output:

- `python3 contracts/validate_examples.py` → exit 0, "Validated 2 request and 3
  response examples against answer_api_contract".
- `./gradlew :shared:jvmTest --rerun-tasks` → **BUILD SUCCESSFUL, 129 tests / 0
  failures** across 15 classes (`CitationPresentationTest` 23, `ChatHomeStateTest`
  31, `ChatConversationTest` 9). HEAD baseline census 104 `@Test`; only deltas are
  the two grown suites and the new 23-test class — **no test removed**.
- `./gradlew :shared:testAndroidHostTest --rerun-tasks` → **BUILD SUCCESSFUL, 118
  tests / 0 failures**.
- `./gradlew :desktopApp:build :androidApp:assembleDebug --rerun-tasks` →
  **BUILD SUCCESSFUL, 72 tasks executed**, exit 0, `androidApp-debug.apk`
  repackaged.
- `./scripts/init.sh --verify` → **BUILD SUCCESSFUL, exit 0**.
- `./gradlew :shared:compileKotlinIosSimulatorArm64 --rerun-tasks` → **BUILD
  SUCCESSFUL** (unmodified tree: the new `commonMain` code compiles for iOS).
- `./gradlew :shared:iosSimulatorArm64Test --rerun-tasks` → **BUILD SUCCESSFUL,
  129 tests / 0 failures**, including `chat.CitationPresentationTest` **23/0 on
  Kotlin/Native** (a second toolchain for the regex / `Char.isWhitespace()` /
  date-parsing code). Reaching it required temporarily stripping a pre-existing
  comma-in-test-name error at `lands/AddLandStateTest.kt:134` and
  `theme/ManijeroColorsTest.kt:269` (present at HEAD, not caused by this feature,
  whose own test names contain no comma); both files were then restored
  byte-identical to HEAD.
- `grep -rn "Color(0x" …/manijero --include=*.kt` → matches only
  `theme/ManijeroColors.kt`.
- Privacy grep `println|Log\.|Logger|printStackTrace|NSLog` over
  `shared/src androidApp/src desktopApp/src` → **no matches** (exit 1).
- `grep -rn "lastResponseStatus" …/App.kt` → **zero** occurrences (nothing is
  rendered from the mutable state).
- Copy fidelity: the nine new strings are **byte-for-byte identical** to the spec
  table; `strings.xml` numstat `9 0` → no existing string changed or deleted, and
  `chat_home_submitted` is intact; no duplicates.
- `git diff --check` → clean.

## Independent behavior reproduction (validator probe, 11 tests, all passing)

Created, run, and deleted before returning:

- **Text fidelity.** A conforming reply split into `Reference` segments, when each
  reference is substituted back to `[n]` and concatenated, reproduces the server
  `answer` byte-for-byte for `[1]`, `[1][2]`, reordered, repeated, trailing, and
  newline-edged marker runs.
- **Fail-closed degradation (carried F1).** A non-prefix payload such as
  `[2]` with a single source, plus the sparse, out-of-range, non-numeric
  (`[1.5]`, `[ 1 ]`, `[1 1]`) and leading-zero (`[01]`, `[007]`, `[0]`) cases,
  yields no numbered card and the body stays exactly as received. The
  F1 reproduction (`DraftAnswer`-shaped `[2]` with one source) is asserted
  directly.
- **Abstention / clarification gate.** A non-`answered` status with a malformed
  payload that carries `sources` and a marker in the body renders no card,
  reference, figure, date, or link, and the pinned message stays verbatim.
- **Per-entry sources.** Over three turns ending in a malformed abstention, each
  entry keeps its own `sources` and references; nothing reads
  `lastResponseStatus`.
- **Card mapping.** Title/issuing body/location/excerpt (including `\n` and
  accents) map verbatim and in payload order; a blank verification date becomes
  `null`; a non-`yyyy-MM-dd` shape is returned unchanged.
- **URL guard matrix.** 4 accepted (canonical `https://host.tld/...` forms) and 16
  refused (`http`, `HTTPS://`, `javascript:`, `mailto:`, `ftp:`, `tel:`,
  scheme-relative, blank, hostless, whitespace/control-containing).

## Spec conformance (by reading the code, not only tests)

- **Marker → card only when conforming.** `answerSourcePresentation` computes
  `conforming = allCanonical && markerNumbers == (1..sources.size).toSet()`;
  references and card numbers (`index + 1`) exist only in that branch. `buildSegments`
  always reconstructs the whole body, and a non-conforming payload returns a single
  `Text(answer)`.
- **https-only link guard, no allowlist.** `openableOfficialUrl` accepts only a
  lowercase `https://` scheme with a non-blank dotted host and no whitespace/control
  character; there is deliberately no client-side domain allowlist (catalog policy
  stays server-side).
- **Sources are a faithful copy.** `ChatMessage.sources` is written at exactly one
  site (`ChatHomeState.kt` `ResponseReceived`, passing `response.sources`
  unchanged); nothing is filtered, reordered, deduplicated, or stored from
  `lastResponseStatus`. Cards render in payload order.
- **UI.** `ChatBubble` gains a defaulted `annotatedText: AnnotatedString? = null`
  (existing call sites unchanged); reference numerals use
  `BaselineShift.Superscript` with `onSurfaceVariant`; the card section shows
  `Fuente n`, title, `Publica:`, `Parte del documento:`, `Comprobado el …`, and the
  excerpt in an always-visible `surfaceVariant` block inside one
  `mergeDescendants` node, followed by a separate `Button` labelled
  `Abrir documento oficial` with a source-naming `contentDescription`. The click is
  a best-effort `runCatching { LocalUriHandler.current.openUri(link) }` with no
  logging; a `null` link shows the pinned unavailability line. No badge, success
  colour, or "verificado" affordance was added.
- **No duplicated code-owned notice.** The server `answer` is the only body text;
  the client adds no lead-in, notice, disclaimer, source, figure, date, or next step.
- **Three states preserved.** The accepted neutral answer / caution abstention /
  danger failure treatments and the clarification path are unchanged.

## Security assessment

Feature-scoped review found no issues. No new I/O, network surface, endpoint,
engine, permission, dependency, or module; no `println`/`Log`/exception-text
logging; URLs, excerpts, questions, payloads, and land data are never logged or
sent anywhere new; the https-only guard refuses `javascript:`, `mailto:`, `ftp:`,
`tel:`, scheme-relative, hostless, and blank targets; `runCatching` prevents a
platform `openUri` refusal from crashing the screen and logs nothing.

## Documentation / harness state

`CONSTRAINTS.md` gained exactly one "Client source cards" **MUST** rule.
`docs/specs/response_states.md` gained the one-line R5-closed note the spec
requires. `DESIGN.md`, `AGENTS.md`, `docs/risks-and-open-questions.md`,
`knowledge/README.md`, and `scripts/init.sh` were correctly left unchanged. The
backend-owned `grounded_answer_generation` F1 hardening and the unconditional
`[n] == sources[n-1]` sentence in `knowledge/README.md` were **not** changed here
(follow-up N7).

## Non-blocking findings

- **N1 (docs/harness; mandatory before commit).** `feature_list.json` evidence was
  empty and `PROGRESS.md` was untouched during implementation. Closed by the
  orchestrator at acceptance time (status `accepted`, evidence entry, session-log
  row, feature-evidence section, and this record).
- **N2 (evidence gap, disclosed).** The feature-list link-reachability smoke
  (open each card's control on Android/Desktop and observe the cited document) was
  not run: it requires a temporary non-committed fake `AnswerService` because the
  shipped default is `UnavailableAnswerService`, there is no `/ask` route, and the
  corpus is empty. The deterministic chain (payload `url` → `card.link` unchanged →
  the single `LocalUriHandler.openUri(link)`) is covered by tests and inspection;
  only the OS-level browser hand-off is unverified. Greyscale and
  `widthDp = 320`/`fontScale = 2f` rendered review are structural + compiled-preview
  based. Owner: `chat_accessibility`. No E2E or automated UI coverage is claimed.
- **N3 (minor).** `formatVerificationDate("2026-02-31")` → `"31/02/2026"` (day
  range 1..31 only, no calendar check). Only reachable from a payload that already
  violates the contract's `format: date`; nothing invented.
- **N4 (minor).** A 4-digit token (`[1234]`) never matches `\d{1,3}`, so it stays
  literal text and cards stay unnumbered — consistent with fail-closed.
- **N5 (by design).** A non-conforming payload still shows unnumbered cards
  (title/excerpt/link) while the raw token stays in the body — exactly spec §2
  rule 2.
- **N6 (by design).** `answerSourcePresentation` runs once per composition without
  `remember` — intentional per spec rule 6.
- **N7 (escalated, backend-owned).** The `grounded_answer_generation` F1 hardening
  (renumber or reject a non-prefix cited set) and the unconditional
  `[n] == sources[n-1]` sentence in `knowledge/README.md` must be scheduled before
  any hosted-model path; the client is safe either way.
