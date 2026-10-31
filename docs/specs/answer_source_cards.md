# Feature Spec: `answer_source_cards`

## Source metadata

- **Feature:** `answer_source_cards` — Inspect cited sources (`client`), `not_started` at planning (2026-10-13).
- **Depends on:** `response_states`, `visual_foundation` (both accepted).
- **Source behavior:** A person can see the source title, relevant location, verification date, and open the official source from an answer.
- **Source verification:** Open each source card in a sample answer and confirm its link reaches the cited official document.
- **Feature-list note:** Display critical source excerpts prominently when required by the answer policy.
- **Handoffs / carried findings received:**
  - `docs/validations/response_states.md` **R5**: `[1]`-style markers render verbatim in the answer until this feature ships cards; owned here.
  - `docs/validations/response_states.md` **N3**: the preview samples in `App.kt` carry no markers; this feature is expected to add them.
  - `docs/validations/grounded_answer_generation.md` **F1** (low–medium): the invariant "marker `[n]` always means `sources[n-1]`" holds only while the cited set is the prefix `1..m`; a non-prefix cited set is accepted by `verify_draft` and would make `[2]` point at a one-element `sources`. F1 says "fix before the hosted-model path is enabled or before `answer_source_cards` maps markers to cards". Handled here **from the client side** (never link a non-conforming payload) with the backend hardening recommended as a separate slice (see R1/U1).
  - `grounded_answer_generation` handoff: markers `[n]`, the notice, and verification dates are presented here and **the code-owned notice must not be duplicated**.
  - `safe_abstention` / `CONSTRAINTS.md`: an abstention carries `sources: []` and must never gain a source, figure, or date.
  - `DESIGN.md` lines 84 and 78: "place citations beside relevant claims; provide a readable source card and the verification date" but "never use a confident visual treatment to imply that an answer is legally definitive".

## Goal and boundaries

Make every cited document of an answered reply inspectable **inside the transcript**: each `AnswerSource` the server returned becomes one readable card (title, issuing body, location, verification date, always-visible excerpt) with one control that opens the official document, and each `[n]` marker in the reply body becomes a matching reference number instead of a raw bracket. The client invents no source, excerpt, date, link, or claim: it renders exactly the decoded payload, keeps every entry's own sources, and degrades to the untouched server text when the payload's markers and `sources` do not line up.

**In scope**

- Per-entry `sources` on the assistant transcript entry, copied at the single creation site (never from `lastResponseStatus`).
- One pure, Compose-free presentation layer: marker tokens → reference numbers, `sources` → cards, https-only link guard, verification-date formatting.
- One source-card section under an answered reply, with a numbered card per source and one `Abrir documento oficial` control, plus an unavailability line for an unopenable URL.
- Nine new pinned Spanish strings, four refreshed/added previews, and pure `commonTest` coverage.
- Closing R5 for conforming payloads, and preserving the accepted `response_states` treatments unchanged for abstained, clarification, and failure states.

**Non-goals**

- No change to `contracts/`, `backend/`, `knowledge/`, or the accepted wire shape. In particular **no `critical` flag on the wire**: `backend/app/generation.answer_source` deliberately drops the retrieval-local `critical` field, so this feature cannot highlight only the critical excerpts (see R4/U3). Any flag is an `answer_api_contract` change owned elsewhere.
- No marker-driven retrieval, no marker-specific claim extraction, no re-wording, re-ordering, translating, shortening, or re-generating of the answer text; only the `[n]` token becomes a reference numeral.
- No inline tappable citation links, no scroll-to-card, no transcript auto-scroll (carried F3), no copy/share of the link, no in-app browser or document viewer, no caching or download of documents.
- No land context/`land_scope` presentation (`land_clarification`, `answer_land_scope` own them) and no change to the abstention, clarification, working, or failure notices.
- No full screen-reader/focus/large-text audit (`chat_accessibility` owns it); no new dependency, Gradle module, navigation, ViewModel, DI, or permission; no logging or display of URLs, excerpts, questions, or land data.

## Job story

When the assistant gives me an answer, I want to see which official document it came from, where in that document, when it was checked, and to be able to open it myself — so I can trust the answer enough to check it, and so I never have to understand what `[1]`, `[2]` or a bare web address mean on my own.

## Acceptance scenarios

### An answered reply shows each cited source

Given a contract-valid `answered` response carrying one or more `AnswerSource`s arrives, when its entry is rendered, then one card per source appears **in payload order**, each showing the source title, its issuing body, its location, its verification date, and its excerpt as an always-visible block (never collapsed, never truncated by the client), each card carries a visible `Fuente n` number, and no card is added for a reply that has no sources.

### The card's link reaches the cited official document

Given a card whose `url` is an https URL, when the person selects `Abrir documento oficial`, then the platform opens exactly that URL through the composition's URI handler and nothing else; the control is a normal Material control with the visible label and an accessible description naming the source title. Given a `url` that is not an openable https URL (blank, no host, or a non-https scheme), then no control is offered and the card shows the pinned plain-Spanish unavailability line instead — the client never opens a non-https target and never crashes the screen when the platform refuses to open a link.

### Markers become references to the right card, or to none

Given an answered reply whose distinct `[n]` markers are exactly `1..sources.size`, then reference `n` is the card numbered `n`, and the claim text is unchanged except that each `[n]` token is rendered as a superscript numeral. Given a payload whose markers do not line up with `sources` (absent, sparse, out-of-range, or non-numeric markers — carried finding F1), then **no** marker is rewritten and **no** card is numbered, so the client can never point at the wrong document; the reply body stays exactly as received.

### An abstention never shows a source

Given any `abstained` (or clarification) entry, when it is rendered, then no card, reference numeral, figure, date, or link is added even if a malformed payload carried a `sources` entry, and the pinned message stays verbatim. The already-accepted caution treatment is unchanged.

### Each answer keeps its own sources

Given an answered reply with cards followed by another turn, when the transcript is rendered, then the earlier entry keeps its own cards and references and nothing is rendered from the mutable `lastResponseStatus`; sources are copied once, at the site that appends the assistant entry.

### Nothing else changes

Given the feature ships, when the existing suites run, then the composer, working indication, character-limit copy, suggested questions, clarification acknowledgement, failure notice, land screens, theme values, contract validator, and backend behave exactly as before, with no previously passing test regressing and the three accepted transcript treatments (neutral answer, caution abstention, danger failure) intact.

### Copy and accessibility of the cards

Given a card is shown, when assistive technology reads it, then the title, issuing body, location, verification date, and excerpt are read as one merged node, `Abrir documento oficial` is a separate focusable control whose description names the source, and the reference numeral is distinguished by position/size rather than colour alone. The answered reply with its cards renders without clipping or horizontal overflow at `widthDp = 320` and `fontScale = 2f`.

## Technical approach

### 1. Per-entry sources (`ChatHomeState.kt`)

```kotlin
data class ChatMessage(
    val speaker: Speaker,
    val text: String,
    /** Assistant-only: the decoded response state. Never read for [Speaker.USER] entries. */
    val answerStatus: AnswerStatus = AnswerStatus.answered,
    /** Assistant-only: the `sources` the response arrived with, in payload order. */
    val sources: List<AnswerSource> = emptyList(),
)
```

- `ResponseReceived` (the only assistant-entry creation site) passes `response.sources` unchanged; nothing is copied, filtered, reordered, or deduplicated by the client.
- The default keeps every existing `ChatMessage` construction compiling. Only `answered` entries may render cards; the gate is the pure layer below, not the storage (which stays a faithful copy of the payload).
- `lastResponseStatus`/`landIdsToChoose` keep their clarification meaning and are never read for rendering.

### 2. Pure presentation layer (new `chat/CitationPresentation.kt`, Compose-free, I/O-free)

```kotlin
sealed interface AnswerSegment {
    data class Text(val text: String) : AnswerSegment
    data class Reference(val number: Int) : AnswerSegment
}

data class SourceCard(
    val number: Int?,        // null when the reply's cited set does not line up with `sources`
    val title: String,
    val issuingBody: String,
    val location: String,
    val verifiedOn: String?, // formatted for display; null only when the payload value is blank
    val excerpt: String,
    val link: String?,       // openable https URL, or null
)

data class AnswerSourcePresentation(val segments: List<AnswerSegment>, val cards: List<SourceCard>)

fun answerSourcePresentation(status: AnswerStatus, answer: String, sources: List<AnswerSource>): AnswerSourcePresentation
fun openableOfficialUrl(url: String): String?
fun formatVerificationDate(isoDate: String): String
```

Rules, all deterministic and unit-testable:

1. `status != answered` → `AnswerSourcePresentation(listOf(Text(answer)), emptyList())`: no card, **no marker rewriting**, so an abstention keeps its pinned message verbatim and can never show evidence even from a malformed payload.
2. Otherwise split `answer` on the marker token `\[(\d{1,3})\]`. The reply is *conforming* when the distinct marker numbers, sorted, equal `1..sources.size` — the invariant `backend/app/generation.py` documents. Conforming: each token becomes `Reference(n)` and cards are numbered by payload position (`index + 1`), so reference `n` is card `n`. Non-conforming (F1): every token stays literal text and every card has `number = null`, so the client never shows a wrong correspondence.
3. The claim text is never altered: for a conforming reply, replacing each `Reference(n)` with `[n]` and concatenating the segments reproduces `answer` byte-for-byte; for a non-conforming or non-answered reply the single `Text` segment equals `answer`.
4. `openableOfficialUrl` returns the URL unchanged only when it starts with `https://` (case-sensitive, as the catalog gate stores it), has a non-blank host containing a dot, and contains no whitespace or control character; otherwise `null`. `http`, `javascript:`, `mailto:`, blank, and hostless values are refused. There is deliberately **no client-side domain allowlist**: approved official hosts are catalog policy and duplicating it in the client would silently drift.
5. `formatVerificationDate` converts a strict `yyyy-MM-dd` with a plausible month/day to `dd/MM/yyyy`; any other shape is returned unchanged (never invent or repair a date). Blank becomes `null` on the card, which then omits the date line.
6. The layer holds no state and does no I/O; the UI calls it per entry during composition.

### 3. Source-card UI (`App.kt`)

- `ChatMessageBubble`'s `Speaker.ASSISTANT` / `AnswerStatus.answered` branch renders a `Column` of the existing neutral `Asistente` card (body now an `AnnotatedString`) followed, when `cards` is not empty, by a `SourceCardsSection`. The `answered` card keeps its `surface`/`outlineVariant` look and gains no badge, checkmark, success colour, or "verificado" affordance.
- `ChatBubble` gains one defaulted parameter, `annotatedText: AnnotatedString? = null`; when present it renders instead of the plain `String` body, so every existing call site is unchanged. Reference numerals are appended inside a `SpanStyle(baselineShift = BaselineShift.Superscript, color = MaterialTheme.colorScheme.onSurfaceVariant)` — a position/size cue first, colour second, and never a tappable link (the card holds the large, labelled control).
- `SourceCardsSection(cards)` renders the pinned heading and one card per source: `Fuente n` (when numbered) · title · `Publica: …` · `Parte del documento: …` · `Comprobado el …`, all inside one `semantics(mergeDescendants = true)` node, then the excerpt in its own `surfaceVariant` block with the pinned excerpt label, then the control.
- The control is a `Button` labelled `Abrir documento oficial` with `Modifier.semantics { contentDescription = <pinned description with the source title> }` (the `land_list_edit_description` pattern). Its `onClick` is `runCatching { LocalUriHandler.current.openUri(card.link) }`: best-effort, no crash when the platform refuses (Desktop/Linux AWT), no logging, no URL or excerpt logged. When `link == null` the pinned unavailability line is shown instead of the control.
- Card order is payload order; nothing is reordered, merged, or deduplicated client-side.

### 4. Previews (all inside `ManijeroTheme`)

Update `ANSWERED_SAMPLE` (preview-only) to carry `[1]` markers, add a preview-only `SOURCE_SAMPLE` list built **verbatim** from the accepted `contracts/examples/response-answered.json` source, and add: answered reply with one card, answered reply with two cards (the same accepted sample duplicated; preview-only, no invented title, body, date, URL, or excerpt), and a card at `widthDp = 320, fontScale = 2f`. The existing abstained and both-states previews stay and now also demonstrate that no card appears for an abstention.

### 5. Copy contract (ship verbatim)

| Key | Text | Used for |
|---|---|---|
| `chat_source_section_title` | `Fuentes` | heading above the cards |
| `chat_source_label` | `Fuente %1$d` | the number label of a conforming card |
| `chat_source_issuing_body` | `Publica: %1$s` | `issuing_body` |
| `chat_source_location` | `Parte del documento: %1$s` | `location` |
| `chat_source_verified_on` | `Comprobado el %1$s` | formatted `verified_on` |
| `chat_source_excerpt_label` | `Texto del documento` | the excerpt block label |
| `chat_source_open` | `Abrir documento oficial` | the link control |
| `chat_source_open_description` | `Abrir el documento oficial: «%1$s»` | the control's accessible description (source title) |
| `chat_source_link_unavailable` | `No se puede abrir este enlace desde aquí.` | shown when the URL cannot be opened |

Plain Spanish, established tú voice, no digit and no date in any client-authored string, no legal claim, no disclaimer (the code-owned notice is already inside the answer body and must not be duplicated). Do not change or delete any existing string, including the now-unused `chat_home_submitted`.

### 6. Deliberately not done

- No `critical` highlighting: the accepted payload has no criticality field (`ANSWER_SOURCE_KEYS`), so the client shows **every** cited excerpt prominently and always visible rather than pretending to know which one is critical; a flag is an `answer_api_contract` change (U3).
- No client-authored explanation of a marker, no "cita verificada"/"fuente oficial" wording that would add certainty, and no client next step or phone number.
- No change to the failure notice, working notice, clarification acknowledgement, composer, or the abstention treatment.

## Expected file changes

- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/ChatHomeState.kt`: `sources` on `ChatMessage`; `response.sources` in `ResponseReceived`.
- **Add** `shared/src/commonMain/kotlin/com/jamarglex/manijero/chat/CitationPresentation.kt`: `AnswerSegment`, `SourceCard`, `AnswerSourcePresentation`, `answerSourcePresentation`, `openableOfficialUrl`, `formatVerificationDate` (Compose-free, standard library only).
- **Modify** `shared/src/commonMain/kotlin/com/jamarglex/manijero/App.kt`: the `annotatedText` parameter on `ChatBubble`, the answered branch + `SourceCardsSection`/`SourceCardView`, the refreshed and new previews, preview-only samples.
- **Modify** `shared/src/commonMain/composeResources/values/strings.xml`: the nine strings above.
- **Add** `shared/src/commonTest/kotlin/com/jamarglex/manijero/chat/CitationPresentationTest.kt`: conforming mapping and byte-for-byte text fidelity, non-conforming degradation, abstention gate (with a malformed source), card field mapping and order, blank date, URL guard, date formatting.
- **Update** `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatHomeStateTest.kt`: an answered response appends one assistant entry carrying the decoded sources in order; a later turn does not change the earlier entry's sources; an abstained entry carries none; clarification still appends no entry.
- **Update** `shared/src/commonTest/kotlin/com/jamarglex/manijero/ChatConversationTest.kt`: a fake `AnswerService` returning an answered response with a source yields one assistant entry whose `sources` equal the payload.
- **Update** `CONSTRAINTS.md` during implementation with one short client MUST rule (see durable docs).
- **Do not modify**: `contracts/`, `backend/`, `knowledge/`, `theme/`, `lands/`, `androidApp/`, `desktopApp/`, `shared/src/iosMain/`, any Gradle file or version catalog, `scripts/init.sh`, and `feature_list.json`/`PROGRESS.md` while implementing.

## Visual design and accessibility impact

Uses accepted theme roles only: `surface` + `outlineVariant` for the reply and card, `surfaceVariant`/`onSurfaceVariant` for metadata and the excerpt block, `primary` for the one control, all within the existing 720dp content width; no raw colour, no new token, no confidence affordance. The reference numeral is a superscript numeral (matching the card number) so the citation cue is never colour-only. Each card is one merged semantics node plus a separate `Button` carrying a `contentDescription` that names the source, so a screen-reader user knows which document the control opens; `Button`/`TextButton` keep Material's 48dp minimum target and Desktop focus behaviour. Long titles, locations, and excerpts wrap and the screen still scrolls; at `fontScale = 2f` nothing is clipped and there is no horizontal overflow because the URL is never rendered as text. Known limits owned elsewhere: no transcript auto-scroll (carried F3, `chat_accessibility`), Desktop text scaling is preview-based (`visual_foundation` U3), and the full screen-reader/focus policy is `chat_accessibility`.

## Durable documentation impact

| Document | Action | Reason |
|---|---|---|
| `CONSTRAINTS.md` | **Update during implementation** | One client MUST rule: every assistant entry MUST render only the `sources` its own decoded response carried (never from `lastResponseStatus`); the client MUST NOT invent a source, excerpt, date, or link, MUST open only an https URL, MUST NOT render a source, reference, figure, or date on an abstention, and MUST NOT alter the answer's claim text (only `[n]` tokens may become references, and only when the cited set lines up with `sources`). `chat_accessibility` and `answer_land_scope` render this transcript next. |
| `docs/specs/response_states.md` | **Append one line after implementation** | Record R5 as closed from this side for conforming payloads (precedent: `network_error_recovery` recorded F2 in `chat_question_submission.md`). The accepted behavior itself is not revised. |
| `docs/validations/grounded_answer_generation.md` / `knowledge/README.md` | **Not changed here; escalate** | F1's backend hardening and the unconditional `[n] == sources[n-1]` sentence in `knowledge/README.md` are backend-owned; this feature only refuses to link a non-conforming payload (R1). |
| `DESIGN.md` | Not needed | Lines 84 and 78 already require exactly this treatment (readable source card, verification date, no confident legal-certainty affordance); no token or surface is added. |
| `AGENTS.md`, `CONTEXT.md`, `docs/archive/build-brief.md`, `docs/domain-model.md` | Not needed | No product, glossary, or domain change; the operating rules (plain Spanish, accessibility, commonMain UI, minimize land context, no invented legal facts) are already authoritative. |
| `docs/risks-and-open-questions.md` | Not needed | The "unsupported or outdated legal answer" mitigation already names visible citations and verification dates; this implements it and opens no new question that needs the register. |
| `ARCHITECTURE.md` | Not needed | It does not exist; no module, boundary, or dependency is added. |
| `scripts/init.sh` | Not needed | No new mode; it must not start a service. |
| `feature_list.json`, `PROGRESS.md` | After verified implementation only | Record evidence, status, and the F1/link-evidence limitations then; planning does not touch them. |

## Risks and open decisions

- **R1 F1 depends on the prefix set (backend-owned root cause).** Marker `[n]` means `sources[n-1]` only when the cited set is `1..m`; a non-prefix payload (accepted by `verify_draft`, unreachable from the enabled extractive generator) would silently point at the wrong document. This feature removes the client's exposure by linking and numbering only a conforming payload (U1), but the backend invariant itself stays unenforced: recommend the orchestrator schedule the small backend hardening (renumber or reject a non-prefix set) before any hosted-model path.
- **R2 One card per source can outweigh the answer.** A reply with several sources renders a long card list; the section is intentionally not collapsed because the feature requires the excerpt to be prominent, and the reply card still comes first. If real payloads prove too long, progressive disclosure is a follow-up decision, not a silent truncation.
- **R3 The excerpt is shown for every source, not only a "critical" one.** The wire carries no criticality (U3), so the client shows all cited excerpts always visible. This over-satisfies the feature note but never claims to know which excerpt is critical.
- **R4 Marker rendering changes the visible body.** Only `[n]` tokens change; the claim text is byte-identical after substituting the token back (tested). Do not let a later change reflow, trim, or rewrite the answer while adding references.
- **R5 Desktop link opening can fail.** `LocalUriHandler` on Desktop goes through `java.awt.Desktop.browse`, which throws where BROWSE is unsupported (known Linux case). The call is best-effort with no crash and no logging; the limitation is reported rather than hidden, and no second UI path (in-app browser) is added.
- **R6 Fail-open details.** `ChatMessage.sources` defaults to `emptyList()` and the reference gate fails closed (no link/annumeration when anything is off), so a future creation site that forgets `sources` shows no cards rather than a wrong one. Only `ResponseReceived` creates assistant entries today, tests assert the copied payload, and the `CONSTRAINTS.md` rule guards it.
- **R7 No real answer exists to inspect.** With an empty corpus and no `/ask` route, the running apps can only reach this UI through the accepted fixture (temporary fake) or a preview; state that instead of implying an end-to-end citation smoke.
- **U1 Whether the backend F1 hardening lands before this feature or after** (client stays safe either way; the decision belongs to the orchestrator).
- **U2 Whether a reference numeral should also be tappable to its card** (needs scroll-to-item, currently impossible without transcript scrolling, carried F3); `chat_accessibility` can revisit.
- **U3 Whether `AnswerSource` should gain a criticality flag** so only the critical excerpt is highlighted: a contract change owned by `answer_api_contract`/`grounded_answer_generation`; do not add it client-side.
- **U4 Whether `published_or_updated_on` should also be shown** next to the verification date (the medium risk "obsolete rule beside a current one" argues for it); out of the declared scope here, revisit with `answer_land_scope`/`land_safety_evaluation`.

## Focused verification

`./scripts/init.sh --feature <feature-id>` runs exactly the block below. It is the feature-scoped
tier of `./scripts/init.sh --fast`, and the cheapest check that still touches what this feature
changed; `./scripts/init.sh --verify` remains the full gate.

<!-- verify:start -->
```sh
python3 contracts/validate_examples.py
./gradlew :shared:jvmTest --tests CitationPresentationTest --tests ChatHomeStateTest --tests ChatConversationTest
```
<!-- verify:end -->

## Appendix

The planning and verification record for this feature — repository research, implementation
plan and tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and the feature evidence — moved verbatim to
[`docs/archive/specs/answer_source_cards.appendix.md`](../archive/specs/answer_source_cards.appendix.md) on 2026-10-17 to keep this contract short.
`docs/validations/answer_source_cards.md` remains the authoritative acceptance record.
