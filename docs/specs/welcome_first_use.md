# Explain what the assistant can do, its limits, and data handling on first use

## Source metadata

- `id`: welcome_first_use · `area`: client · `depends_on`: chat_screen_refresh, help_privacy_refresh, coverage_and_help (all accepted) · `status` at planning: not_started
- User-visible behavior: until the person dismisses it, the chat screen opens with a short plain-Spanish welcome card that summarizes what the assistant can and cannot answer, where to get human help, and how land data is handled. `Ayuda` offers `Ver bienvenida` to show it again.
- Verification: pure state and copy-guard tests, Desktop and Android store tests, Compose interaction tests, compile checks, and host screenshots (commands in Focused verification).
- Source: MVP screen 1 "Welcome / first use" and §16 "Explain data use in plain Spanish before first use" in [`docs/archive/MasterPlanV3.md`](../archive/MasterPlanV3.md); the `CR1` slice deferred by [`coverage_and_help`](coverage_and_help.md) and [`land_data_disclosure`](land_data_disclosure.md).
- Notes — owner decisions, 2026-11-02:
  1. **Form:** a dismissible welcome card at the top of the chat screen, shown on first launch only. It is not a full-screen gate and not a multi-page intro. Dismissal is remembered locally on the device.
  2. **Ayuda link:** the `Ayuda` (coverage/help) screen gets one new `Ver bienvenida` link that shows the card again in chat.
  3. **Copy:** new plain-Spanish text that summarizes the accepted coverage, limits, and privacy facts. It adds no new fact or promise, and every sentence traces to an accepted string (see the copy table).
  4. **Acceptance:** the independent validator's accept is final. No owner walkthrough is required, and there is no manual owner-walkthrough acceptance check.
- Planner interpretation of decision 1, open to owner override: "first launch only" means the card shows every time the chat screen renders **until it is dismissed**. It does not hide by itself after one launch. The launch tab is unchanged: Android and Desktop still open on `Mis terrenos` (`initialDestination`), so a person sees the card the first time they open `Asistente`.

## Goal

Before relying on the assistant, a person with little computer experience learns in one calm card what it is built to answer, what it will not answer, who to ask instead, and what stays on the device. They can hide the card with one named action and get it back from `Ayuda`.

## Non-goals

- No full-screen gate, no multi-page intro, no blocking of the composer, and no change to the launch tab or to any existing route.
- No new fact, promise, contact detail, deadline, amount, legal claim, or land-setup wizard. No links inside the card.
- No change to accepted strings, coverage or privacy screen copy, the chat footer, or abstention and failure copy.
- No server-side state, account, analytics, or "seen" telemetry. Nothing is logged.
- No iOS host wiring. With no store injected (iOS scaffold, previews, smoke drivers, existing tests), the card and the link are absent.
- No usability, screen-reader, or device evidence claim. That belongs to `usability_session`.

## Job story

When I open the assistant for the first time, I want a short explanation of what it can help with, what it cannot, and what happens to my land data, so I can trust it for the right things and know where to ask instead.

## Acceptance Scenarios

### 1. First use shows the card

Given a device where the card was never dismissed · When the chat screen renders · Then the welcome card is the first element on the page, above the hero. It shows the pinned title, the four body lines, and one `Entendido` button. The composer, suggestions, and footer remain usable below it.

### 2. Dismissal hides it and is remembered

Given the card is visible · When the person activates `Entendido` · Then the card disappears at once and the dismissal is written to the device store. After a restart (a new `App` with the same store), the chat screen shows no card.

### 3. `Ver bienvenida` shows it again

Given the card was dismissed · When the person opens `Ayuda` and activates `Ver bienvenida` · Then the app goes to the chat screen with the card visible at the top and `Asistente` selected. Showing it again writes nothing. Activating `Entendido` hides it again, and it stays hidden after a restart.

### 4. Storage failure is forgiving

Given the store cannot be read · When the chat renders · Then the card is shown (an unknown state is treated as not dismissed). Given the store refuses the write · When `Entendido` is activated · Then the card still hides for this session, no error is shown, nothing is logged, and the card may appear again on the next launch.

### 5. Copy adds no new facts

Given the welcome strings · Then they match the copy table verbatim, each body line traces to the accepted source keys listed there, and no welcome string contains a digit or the fragments `garantiz` or `correct`.

### 6. Absent store leaves today's app unchanged

Given `App` with no welcome store, or `ChatHomeScreen`/`CoverageScreen` called with their default parameters · Then there is no card and no `Ver bienvenida`, and every existing screenshot golden still passes without re-recording.

### 7. Accessible and readable

Given compact width, 2× text, or dark theme · Then the card wraps without clipping, uses theme roles only, and adds **no** `heading()` semantics: the chat keeps exactly one heading, per [DESIGN.md](../../DESIGN.md) "Assistant surface". `Entendido` and `Ver bienvenida` are visible text buttons that keep Material's minimum target size.

## Copy table (new keys in `strings.xml`; pinned verbatim)

| Key | Text | Traces to |
|---|---|---|
| `welcome_title` | Antes de empezar | framing only; no fact |
| `welcome_can` | La app está preparada para responder sobre algunos trámites y ayudas del olivar, según los documentos oficiales revisados. No siempre tendrá una respuesta. | `coverage_intro` |
| `welcome_limits` | No responde cuánto cobrarías, si te corresponde una ayuda ni las prácticas concretas de tu cooperativa. Para eso, habla con tu oficina comarcal agraria o con tu cooperativa. | `coverage_no_personal`, `coverage_no_coop`, `coverage_help_body` |
| `welcome_privacy` | Tus terrenos se guardan en este dispositivo. Al preguntar, se puede enviar tu pregunta y algún dato del terreno. La respuesta se prepara con ayuda de un servicio externo. | `chat_home_privacy_summary`, `privacy_promise_body_2` |
| `welcome_lands` | Puedes empezar sin añadir ningún terreno. Más detalles en Ayuda, donde también puedes volver a ver este mensaje. | `chat_home_description`; `Ayuda` tab; this feature's link |
| `welcome_dismiss` | Entendido | action label |
| `coverage_show_welcome` | Ver bienvenida | owner decision 2 |

## Technical approach

- **State (commonMain, new package `welcome/`).** `WelcomeNoticeStore` interface (`isDismissed(): Boolean`, `markDismissed()`; either may throw). `WelcomeNotice(store)` holds a Compose-observable `visible` flag, initialised once from a guarded read (a throw means visible). `dismiss()` hides the card, then tries one guarded write. `showAgain()` makes the card visible in memory only. `WELCOME_COPY_SOURCES` maps each welcome key to its source keys for the copy guard. The state follows the `ActiveServiceAddress`/`ConnectionController` pattern: no ViewModel, DI, or coroutine.
- **Persistence (device-local, release and debug builds alike).** Android: `AndroidWelcomeNoticeStore` in shared `androidMain` uses its own private preferences file `manijero_welcome` and writes with a synchronous `commit()` (the `AndroidServiceAddressStore` pattern). Desktop: `FileWelcomeNoticeStore(path)` in shared `jvmMain`, with a `desktopWelcomeStorePath()` helper that returns `~/.manijero/welcome-v1.txt`. The file holds the single line `dismissed`; it is dismissed only when that exact first line is present. The value is one boolean with no personal or land data, and it is never sent.
- **Wiring.** `App(…, welcomeNotice: WelcomeNoticeStore? = null)` builds one remembered `WelcomeNotice` when the store is non-null. `MainActivity` and the Desktop `main.kt` inject their stores unconditionally; they are not gated to test builds.
- **Chat.** `ChatHomeScreen(…, showWelcome: Boolean = false, onDismissWelcome: () -> Unit = {})` renders a private `WelcomeCard` before `ChatHero()`. The card is a `ManijeroCard(Outlined)` with a `titleMedium` title (no heading semantics, no live region), four `bodyLarge` paragraphs, and one `OutlinedButton("Entendido")`. `Preguntar` stays the only filled button.
- **Ayuda.** `CoverageScreen(…, onShowWelcome: (() -> Unit)? = null)` adds one full-width `TextButton("Ver bienvenida")` after the help card and before the test-tools card. It is shown only when the callback is non-null. In `App` it calls `showAgain()`, sets `previousSection = Assistant`, and sets `destination = Chat`. `AppNavigation.kt` is unchanged.
- This is an owner-approved new link. It does not conflict with the `help_privacy_refresh` restyle rule in [answers-and-knowledge.md](../constraints/answers-and-knowledge.md) "Coverage disclosure", because existing copy, callbacks, and facts stay unchanged.

## Expected file changes

- `shared/src/commonMain/kotlin/com/jamarglex/manijero/welcome/WelcomeNotice.kt` — create: store interface, state holder, copy-source map.
- `shared/src/androidMain/.../welcome/AndroidWelcomeNoticeStore.kt`, `shared/src/jvmMain/.../welcome/FileWelcomeNoticeStore.kt` — create: platform stores and the Desktop path helper.
- `shared/src/commonMain/.../App.kt`, `chat/ChatHomeScreen.kt`, `coverage/CoverageScreen.kt` — modify: wiring, card, link, previews.
- `shared/src/commonMain/composeResources/values/strings.xml` — modify: add the seven new keys only.
- `androidApp/.../MainActivity.kt`, `desktopApp/.../main.kt` — modify: inject the store.
- Tests: `commonTest/.../welcome/WelcomeNoticeTest.kt`; `jvmTest/.../welcome/{FileWelcomeNoticeStoreTest,WelcomeCopyGuardTest,WelcomeFlowInteractionTest}.kt`; `androidHostTest/.../welcome/AndroidWelcomeNoticeStoreTest.kt`; new captures in `ChatHomeScreenshotsTest`, `HelpPrivacyScreenshotsTest`, `ChatHomeAndroidScreenshotsTest` plus their new PNG goldens only.
- Not expected: `AppNavigation.kt`, `AppShell.kt`, existing strings, existing goldens, backup rule XML, backend, contracts, knowledge, Gradle.

## Visual design impact

UI involved: yes. This adds a chat-top welcome card and one `Ayuda` text link. The [DESIGN.md](../../DESIGN.md) sections "Assistant surface" (one heading, one filled action, compact limit), "Help and privacy surfaces", "Shared component layer", and "Accessibility and validation" apply. On a 360×800 phone the card pushes the hero and suggestions down until it is dismissed. This extends the recorded compact limit and is not a hidden control.

## Durable documentation impact (required)

- `ARCHITECTURE.md`: update — one clause in "Data and platform boundaries" naming the welcome-dismissed flag stores (`manijero_welcome`, `~/.manijero/welcome-v1.txt`). They hold no land or personal data, so the flag is not covered by the land backup exclusion.
- `docs/constraints/client-chat.md`: update — a new "Welcome notice" rule. The card MUST stay dismissible and non-blocking, MUST add no heading or fact beyond its traced copy, and MUST stay in sync when a source string's facts change. Its dismissal MUST stay device-local and never be sent or logged.
- `DESIGN.md`: update — one bullet under "Assistant surface" for the card, and one sentence under "Help and privacy surfaces" for `Ver bienvenida`.
- `docs/screenshot-regression.md` and the golden count in `docs/progress/known-limitations.md`: update for the new captures.
- `AGENTS.md`, `CONTEXT.md`, `docs/domain-model.md`: not needed — no workflow, glossary, or domain change.

## Focused verification (required)

<!-- verify:start -->
```sh
./gradlew --quiet :shared:jvmTest --tests 'com.jamarglex.manijero.welcome.*' --tests 'com.jamarglex.manijero.coverage.*' --tests 'com.jamarglex.manijero.chat.ChatHomeInteractionTest' --tests 'com.jamarglex.manijero.platform.*' --tests AppNavigationTest
./gradlew --quiet :shared:testAndroidHostTest --tests 'com.jamarglex.manijero.welcome.*'
./gradlew --quiet :androidApp:compileDebugKotlin :androidApp:compileReleaseKotlin :desktopApp:compileKotlin
./gradlew :shared:verifyDesktopScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeScreenshotsTest' --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyScreenshotsTest'
./gradlew :shared:verifyAndroidScreenshots --tests 'com.jamarglex.manijero.screenshots.ChatHomeAndroidScreenshotsTest' --tests 'com.jamarglex.manijero.screenshots.HelpPrivacyAndroidScreenshotsTest'
```
<!-- verify:end -->

## Appendix

See [`welcome_first_use.appendix.md`](welcome_first_use.appendix.md) for research, plan, evidence, and the validator checklist.
