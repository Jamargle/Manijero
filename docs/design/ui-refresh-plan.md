# UI Refresh Plan — Manijero

**Status:** draft for product-owner review; the §3.1 palette (Stitch token values plus two `outlineVariant` corrections) was approved on 2026-10-25 and is recorded in `DESIGN.md`. Nothing in this document has been implemented.
**Date:** 2026-10-25
**Scope:** adapt the existing shared Compose UI to the Stitch references and the shared theme, screen by screen and component by component, for Android, Desktop, and iOS-reusable `commonMain`.
**Authority:** existing feature specs own behavior. This plan proposes visual, structural, and scoped content changes; after approval it is sliced into new feature specs with their own acceptance records.

---

## 0. How to read this plan

1. **§1–§3** fix the decisions and the design target.
2. **§4** records the gap between today's UI and the target.
3. **§5** describes every screen, state, and layout.
4. **§6** is the component catalogue.
5. **§7** covers the only data changes.
6. **§8** is the step-by-step work breakdown.
7. **§9** maps the steps to feature specs.
8. **§10–§13** define verification, risks, open decisions, and your review checklist.

The plan deliberately separates **visual adaptation** (no behavior change) from **scoped product additions** (new land fields, search, summary, navigation chrome). The second group must not ride silently inside a restyle.

---

## 1. Confirmed decisions

| ID | Decision | Consequence |
|---|---|---|
| D1 | English project documents; plain Spanish UI copy | This plan and future specs in English; every user string in `strings.xml` |
| D2 | Stitch token palette, approved as written in §3.1 (2026-10-25) | Deep olive primary, limestone-neutral canvas, earth-brown secondary, plum (light) / blue (dark) tertiary; two `outlineVariant` accessibility corrections; contrast tests re-gated |
| D3 | Keep Material 3 default typography | No font assets, no custom `Typography`; identity comes from colour, shape, spacing, imagery |
| D4 | Brand top app bar + adaptive navigation | Three destinations: Asistente, Mis terrenos, Ayuda; bottom bar on compact, rail on wide |
| D5 | Add land search and count/surface/tree summary | Client-side only, derived from local records |
| D6 | Add optional surface, tree count, variety; required zone | Explicit scope change; local-only fields; see §7 and D12 |
| D7 | Visual adaptation only for unsupported mockup content | No profile, cooperative notices, “Oficial” badge, FAQ directory, maps, or eligibility content |
| D8 | Vector brand mark + olive-branch empty-state illustration | Hand-authored vectors in `composeResources`; no image generation, no binary assets |
| D9 | Light and dark in every phase | Both palettes and both preview sets are part of every screen's definition of done |
| D10 | iOS stays reuse-only | All UI in `commonMain`; optional simulator compile smoke; no iOS release work |
| D11 | Custom vector icons drawn from Material Icons geometry | No `material-icons-core` runtime dependency (frozen at 1.7.x against Compose 1.12.1) |
| D12 | Record an explicit product decision superseding the 2026-10-20 field deferral | Append a dated superseding decision to `land_setup_fields_decision`; create a new `land_measurement_fields` spec; note affected owner contracts; never rewrite past acceptance records; state that no new user evidence exists |
| D13 | New fields are local-only | `/ask`, `MinimalLandContext`, backend, and OpenAPI stay unchanged |
| D14 | Search matches name, municipality, zone, variety, water, production | Accent/case-insensitive, client-side |
| D15 | Summary shows count + partial surface + partial trees | Every total states how many lands contributed; never implies completeness |
| D16 | Zone is required free text; variety is a shortlist + “Otra” + mixture + “No lo sé” | Required zone changes the only-name-required rule; existing lands remain readable |
| D17 | Existing lands without a zone stay valid | No forced migration; editing such a land requires completing the zone |
| D18 | Plan → feature specs → implementation | No new `feature_list.json` rows or code before approval |

### Scope-change note (important)

`docs/specs/land_setup_fields_decision.md` accepted on 2026-10-20 explicitly deferred area and notes and kept **only the name required**. D5/D6/D16 change that decision. The plan records the change as a **product decision**, not as a usability finding. The missing target-user evidence must be stated in the new decision record and in the relevant validation records.

---

## 2. Scope, non-goals, and guardrails

### 2.1 In scope

- Shared theme refresh (light + dark) and semantic colours.
- Brand vectors, icon vectors, empty-state illustration.
- Shared visual component library and previews.
- Brand top app bar, adaptive bottom navigation/rail, Scaffold, insets, tab state.
- Visual adaptation of: Asistente, Mis terrenos (empty and populated), Añadir, Editar, Eliminar, Ayuda, Privacidad, chat states, source cards, clarification chooser.
- Land search, count/surface/tree summary, optional zone/variety/surface/trees, with local persistence and tests.
- Accessibility and large-text pass; Android/Desktop screenshots; iOS compile smoke.
- Documentation updates after each accepted feature.

### 2.2 Out of scope

- Accounts, profile, cloud sync, shared ownership, backup/restore.
- Cooperative notices or practices as content; “Oficial” badge; verified-date banner on chat.
- FAQ accordion, OCA/cooperative directory buttons, maps, SIGPAC references, precise parcel mapping.
- Aid calculation, eligibility confirmation, personalized advice.
- New API fields, backend changes, corpus changes, prompt changes.
- Custom fonts, new UI frameworks, test-only dependencies.
- iOS release, store publishing, launcher-icon redesign (recommended as separate polish).
- Navigation deep links, multi-window, tablet two-pane layouts.

### 2.3 Non-negotiable guardrails

- Keep product behavior and Compose UI in `shared/src/commonMain`.
- Keep the existing answer contract: abstention, citations, source excerpts, land scope, clarification, retry semantics.
- Never communicate status by colour alone; chips and callouts always carry text and/or an icon.
- Never imply a land attribute proves eligibility; never infer an unknown value.
- Keep local land data minimal; new fields never enter a request or a log.
- All new copy in `strings.xml`, plain Spanish, no legal jargon.
- Keep the 720 dp readable column; do not stretch a phone layout across Desktop.
- No new dependency unless the plan explicitly names it; this plan adds none.
- Raw hex is allowed only in `ManijeroColors.kt` and the two approved brand/illustration vectors. UI icons stay single-colour and are tinted by the wrapper.
- Every visual step must ship light + dark + large-text previews and pass contrast tests.

### 2.4 Alignment with `MasterPlanV3.md`

The plan stays inside the reconstructed v3.1 scope:

- Android and Desktop are the MVP hosts; all new UI lives in `commonMain` so a later iOS target can reuse it (D1, D10).
- Lands remain local-first; the change adds fields but does not add cloud storage or telemetry.
- Multiple lands remain central: the list, search, and summary make existing lands easier to find; no single-land assumption is introduced.
- The minimum-data rule is preserved: the chat request shape is unchanged, and new fields never leave the device.
- No legal authority is implied: no eligibility, amounts, deadlines, or “verified/official” UI is added. Abstention, citations, and source excerpts keep their current semantics.
- Mockup content outside the MVP (cooperative notices, aid calculations, profiles, maps) is explicitly excluded.
- Plain Spanish, large text, touch, keyboard, and screen-reader support remain acceptance criteria, not polish.

---

## 3. Design target

### 3.1 Palette (approved 2026-10-25, contrast-gated)

The winning palette is the `colors:` token block of the two Stitch exports. Roles are adopted verbatim, with exactly two deviations: `outlineVariant` `#C2C8BD` → `#757C71` in light and `#424942` → `#868E86` in dark, because the Stitch values measure 1.63:1 and 1.97:1 and this repository gates non-text boundaries at 3:1. The Stitch light export's prose colour names (`#385E39`, `#8C6239`, `#D9A036`, `#F4F1EA`) are provenance only; they contradict that file's token block and the screenshots. `scrim` `#000000` is the only role Stitch does not define. **Approved 2026-10-25; the same values are recorded in `DESIGN.md`.**

#### Core tokens

| Token | Light | Dark | Material role |
|---|---|---|---|
| `primary` (`olive-800`) | `#214624` | `#85A886` | `primary` |
| `primaryStrong` (`olive-900`) | `#263724` | `#CFE8CF` | no role; semantic emphasis |
| `canvas` | `#F9FAF4` | `#121612` | `background` |
| `surface` | `#FFFFFF` | `#0D100D` | `surfaceContainerLowest` |
| `text-primary` | `#1A1C19` | `#E1E3DF` | `onSurface` / `onBackground` |
| `text-secondary` | `#424940` | `#C2C8BF` | `onSurfaceVariant` |
| `border` | `#72796F` | `#8C948C` | `outline` |
| `caution` | `#704600` | `#FFD18A` | no role; semantic |
| `caution-surface` | `#FFF2D4` | `#4B350D` | no role; semantic |
| `danger` | `#BA1A1A` | `#FFB4AB` | `error` |

`surface` is the card/input surface, so it maps to `surfaceContainerLowest`; Stitch's own `surface` equals `background`.

#### Full role map

| Material roles | Light | Dark |
|---|---|---|
| primary / onPrimary | `#214624` / `#FFFFFF` | `#85A886` / `#0D1B0E` |
| primaryContainer / onPrimaryContainer | `#385E39` / `#ABD6A7` | `#283C29` / `#CFE8CF` |
| secondary / onSecondary / secondaryContainer / onSecondaryContainer | `#7E562E` / `#FFFFFF` / `#FDC796` / `#79512A` | `#D4C5A9` / `#382E1C` / `#4F422E` / `#F1E5CC` |
| tertiary / onTertiary / tertiaryContainer / onTertiaryContainer | `#602E40` / `#FFFFFF` / `#7B4557` / `#FEB7CC` | `#B8C5D6` / `#222D3B` / `#93A0B0` / `#2B3745` |
| background / onBackground; surface / onSurface | `#F9FAF4` / `#1A1C19`; `#F9FAF4` / `#1A1C19` | `#121612` / `#E1E3DF`; `#121612` / `#E1E3DF` |
| surfaceVariant / onSurfaceVariant / surfaceTint | `#E2E3DD` / `#424940` / `#416741` | `#333532` / `#C2C8BF` / `#ABD0AC` |
| inverseSurface / inverseOnSurface / inversePrimary | `#2F312D` / `#F1F1EB` / `#A7D2A3` | `#E3E3DE` / `#2F312E` / `#456648` |
| error / onError / errorContainer / onErrorContainer | `#BA1A1A` / `#FFFFFF` / `#FFDAD6` / `#93000A` | `#FFB4AB` / `#690005` / `#93000A` / `#FFDAD6` |
| outline / outlineVariant (corrected) / scrim | `#72796F` / `#757C71` / `#000000` | `#8C948C` / `#868E86` / `#000000` |
| surfaceBright / surfaceDim | `#F9FAF4` / `#DADAD5` | `#242C24` / `#1A201B` |
| surfaceContainerLowest / Low / Container / High / Highest | `#FFFFFF` / `#F3F4EE` / `#EEEEE9` / `#E8E9E3` / `#E2E3DD` | `#0D100D` / `#181E18` / `#202820` / `#2C362C` / `#384438` |

Light `background`, `surface`, and `surfaceBright` share `#F9FAF4`; raised cards use `surfaceContainerLowest` (`#FFFFFF`) or the container family. Stitch's `*Fixed` expressive roles are not exposed by this Material version; `primaryFixed` is used only as the Ecológico chip pair.

#### Manijero-only semantic colours

| Token | Light | Dark | Use |
|---|---|---|---|
| `caution` | `#704600` | `#FFD18A` | Uncertainty and limitations, always with text/icon |
| `cautionSurface` | `#FFF2D4` | `#4B350D` | Caution callout background |
| `onCaution` | `#FFFFFF` | `#3A2600` | Text/icon on filled caution |
| `primaryStrong` | `#263724` | `#CFE8CF` | Pressed state and strong emphasis |

These are the only non-Stitch values, apart from the two `outlineVariant` corrections; Stitch has no status roles. There are no `earth`/`sun` tokens: Stitch `secondary` (brown) and `tertiary` (plum/blue) are the decorative accents.

#### Land-attribute chips

| Chip | Light container / ink | Dark container / ink | Anchor pair |
|---|---|---|---|
| Secano | `#FDC796` / `#79512A` | `#4F422E` / `#F1E5CC` | `secondaryContainer` / `onSecondaryContainer` |
| Regadío | `#385E39` / `#ABD6A7` | `#283C29` / `#CFE8CF` | `primaryContainer` / `onPrimaryContainer` |
| Ecológico | `#C2EEBE` / `#002106` | `#C7ECC6` / `#02210A` | `primaryFixed` / `onPrimaryFixed` |
| Neutral / No lo sé | `#E2E3DD` / `#1A1C19` | `#384438` / `#E1E3DF` | `surfaceVariant` / `onSurface` |

Rules:
- `caution` is only for uncertainty/limitations; `secondary` and `tertiary` are decorative/sectional and never a status.
- Chips always carry text, never colour alone.
- Pre-computed representative ratios (to be asserted in tests): onPrimary/primary 10.68:1; onSurface/background 16.35:1; onSurfaceVariant/background 8.86:1; secondary/background 6.14:1; caution/cautionSurface 7.37:1; error/background 6.16:1; outlineVariant/background 4.10:1; chip ink/container pairs 4.56–13.33:1; dark onSurface/background 14.14:1; dark outline/background 5.86:1; dark outlineVariant/surfaceContainerHighest 3.03:1.

### 3.2 Typography

No font assets. Keep `MaterialTheme.typography` (Material 3 defaults, platform font). Use the roles consistently:

| Use | Role | Notes |
|---|---|---|
| Screen title | `headlineMedium` | One heading semantic per screen |
| Hero/section title | `titleLarge` / `titleMedium` | Section titles get `heading()` only when they are real headings |
| Body | `bodyLarge` | 16 sp; never below 14 sp in primary workflows |
| Metadata/helper | `bodyMedium` | 14 sp |
| Buttons/labels | `labelLarge` | 14 sp medium |
| Chips | `labelMedium` or `labelLarge` | Keep 48 dp touch target |
| Citation numerals | superscript `SpanStyle` | Existing behavior |

Consequence of D3: no serif headlines. The “rustic modern” feel is carried by the Stitch palette (olive, brown, plum/blue over limestone neutrals), white tonal cards on a near-white canvas, 16 dp card radii, outlined cards, generous spacing, icons, and the olive illustration.

### 3.3 Shape, spacing, and elevation

- Shapes: small 4 dp (rare), medium 12 dp (inputs, buttons), large 16 dp (cards, sheets, callouts), extraLarge 24 dp (hero, empty-state panel).
- Spacing scale: existing 6/12/24/32/48 plus explicit 4/8/16 for internal rhythm. Screen padding: 24 dp horizontal on compact, 32 dp vertical; 32–40 dp on wide.
- Content column: keep `720.dp` maximum, centred.
- Elevation: flat cards with 1 dp `outlineVariant`; tonal surfaces for grouping; no heavy shadows. App bar and bottom bar use surface + outline, not floating shadows. A soft shadow is allowed only on the empty-state illustration halo.
- Dividers: 1 dp `outlineVariant`, never colour-only status.

### 3.4 Icons and illustration

- 24 dp icons, 2 dp stroke, rounded caps/joins; 20 dp inline; 48 dp minimum interactive target.
- Sixteen UI vectors, hand-authored from Material Icons geometry (Apache 2.0), stored as Android vector XML in `shared/src/commonMain/composeResources/drawable/`:
  `ic_chat`, `ic_lands`, `ic_help`, `ic_search`, `ic_add`, `ic_edit`, `ic_delete`, `ic_back`, `ic_retry`, `ic_send`, `ic_external_link`, `ic_info`, `ic_warning`, `ic_check`, `ic_chevron_down`, `ic_clear`.
- Brand mark: circular olive/leaf mark, 28/32 dp, used in the top app bar only. It is identity, not a status or “verified” indicator.
- Empty-state illustration: olive branch inside a soft `primaryContainer` halo, 160–200 dp, decorative (`contentDescription = null`); the adjacent heading carries the meaning.
- No Material icon dependency. If a glyph is missing, draw it; do not add `material-icons-core` (frozen at 1.7.x, incompatible version line with Compose 1.12.1).
- Record the source geometry and licence note in an appendix of the eventual `brand_vectors` spec.

### 3.5 Adaptive layout

| Width | Navigation | Layout |
|---|---|---|
| `< 600 dp` | Bottom navigation bar, 3 items | Single column, 24 dp side padding, full-width actions |
| `600–839 dp` | Bottom navigation bar, 3 items | Single centred column, 720 dp cap |
| `≥ 840 dp` | Navigation rail (left), labels visible | Top app bar + rail; content centred at 720 dp; rail item targets 48 dp |
| Desktop default | Rail when the window is wide enough | Keep one column; no invented two-pane master/detail |

- Use `BoxWithConstraints` or `WindowWidthSizeClass`-equivalent logic in `commonMain`; do not add an adaptive-layout dependency.
- `Scaffold` owns insets. Composer uses `imePadding`; bottom navigation stays above the keyboard where the platform allows it.
- Top bar: brand mark + “Manijero” on the left; one right-side privacy action (shield + label on wide, icon + accessible label on compact). Hide that action while the Privacy screen itself is open. Tab duplication means no help action is needed in the bar.
- Back behavior: Android system back from a non-chat tab returns to Asistente; from a form returns to Mis terrenos; from Privacidad/Ayuda returns to the previous tab. Desktop keeps explicit back controls in forms only. Verify the common back API at implementation; if unavailable, provide an `expect/actual` host hook rather than dropping system-back support.
- Tab state: selected tab is hoisted in `App`; conversation state survives tab switches. Scroll position per tab is not guaranteed and is not claimed.

### 3.6 Motion

- 150–250 ms fades/size changes for: search results appearing, callouts appearing, tab selection, clarification chooser appearing.
- No essential information only in animation. No looping motion except a small working indicator in chat.
- Respect the platform's reduced-motion signal where available; otherwise keep motion minimal.

### 3.7 Copy rules

- Address the person as “tú”; short sentences; no legal jargon.
- Say what is optional and what is required in words, not asterisks alone.
- Prefer “terreno” for a saved record; use “parcela” only when quoting an official term.
- Never say “verificado”, “oficial”, “te corresponde”, “puedes solicitar” unless the backend answer already provides it.
- Every destructive action names the land and says it cannot be undone.
- New field copy states that measurements and varieties are optional and can stay unknown; zone is required.

---

## 4. Current state and gap analysis

### 4.1 Screens

| Surface | Current implementation | Gap against target |
|---|---|---|
| App shell | `App.kt` destination enum; no Scaffold, app bar, navigation, or insets | Needs top bar, 3-tab adaptive navigation, back rules, Scaffold |
| Asistente | `ChatHomeScreen` in `App.kt`: title, description, transcript, full-width outlined suggestion buttons, composer, text links | Needs hero, chips, assistant/user card styling, send icon, state cards, footer treatment |
| Mis terrenos (populated) | `LandListScreen.kt`: title, description, plain rows with text buttons | Needs summary cards, search, chips, zone/variety/measures, tonal actions, illustration state |
| Mis terrenos (empty) | One sentence + add button | Needs illustration, heading, explanation, primary CTA |
| Añadir | `AddLandScreen.kt`: name, municipality, radio groups; only name required | Needs zone, variety, surface, trees, optional grouping, required markers, styling |
| Editar | `EditLandScreen.kt`: same fields, prefill | Same new fields; legacy lands without zone need the required-zone path |
| Eliminar | `RemoveLandScreen.kt`: confirmation | Needs danger treatment, land identity, safe default focus |
| Ayuda | `CoverageScreen.kt`: plain sections, text links | Needs section cards, icons, limits callout, same content |
| Privacidad | `PrivacyScreen.kt`: plain sections; lists only the three sent attributes | Needs section cards, local-only fields section, clearer local/sent split |
| Chat states | Working notice, failure notice, abstention bubble, source cards, clarification chooser | Keep semantics; restyle to callout/card components |
| Dark mode | Current paired palette, including an off-family blue tertiary | Apply corrected palette and verify every screen |

### 4.2 Components

| Today | Target |
|---|---|
| Raw `Button`, `OutlinedButton`, `TextButton` per screen | A small design-system layer for repeated patterns; plain Material 3 where no shared behavior is added |
| Ad-hoc `Surface` + `RoundedCornerShape(16.dp)` cards | `ManijeroCard` variants |
| No chips, callouts, stat cards, search field, or empty state | New shared components |
| No icons | Hand-authored vector set |
| No app bar or navigation | `ManijeroTopAppBar`, `ManijeroBottomNavigation`, `ManijeroNavigationRail` |
| Repeated screen padding/centring in every screen | `ManijeroScreen` layout wrapper |
| `App.kt` holds the chat screen and all destinations | Extract chat components into `chat/`; keep `App.kt` as composition root and shell only |

---

## 5. Target screens

### 5.1 App shell

```
┌──────────────────────────────────────────────────────┐
│ [brand] Manijero                         [shield] Privacidad │  top app bar
├──────────────────────────────────────────────────────┤
│                                                      │
│   centred content (max 720 dp)                       │
│                                                      │
├──────────────────────────────────────────────────────┤
│   Asistente        Mis terrenos        Ayuda        │  bottom bar (compact)
└──────────────────────────────────────────────────────┘
```

Wide:

```
┌────────────┬─────────────────────────────────────────┐
│ [brand]    │ Manijero                  [shield] Privacidad │
│            ├─────────────────────────────────────────┤
│ ● Asistente│                                         │
│   Terrenos │        centred content (max 720 dp)     │
│   Ayuda    │                                         │
└────────────┴─────────────────────────────────────────┘
```

- Selected destination: indicator + bold label + icon; never colour alone.
- Tab labels always visible.
- No profile/avatar entry.
- The privacy action is a labelled button, not an icon-only control on wide layouts.

### 5.2 Asistente (chat home)

Order:
1. Top app bar.
2. Hero block: small brand/assistant mark, `chat_home_title` as `headlineMedium`, `chat_home_description` as `bodyLarge`. A single calm card with `primaryContainer`/`surface` tones; no “verified” badge, no date, no “Oficial” chip.
3. Suggested questions: `chat_home_suggestions_title` + three wrapping chips with chat/arrow icon; selecting one fills the question field exactly as today (it does not submit). Chips must wrap on large text, not clip.
4. Transcript: existing messages, in order. Empty transcript shows nothing (the hero and suggestions are the starting point).
5. Working state: assistant card with three-dot indicator + `chat_home_working` text, polite live region.
6. Failure state: danger callout with `Reintentar` button; never appended as a message.
7. Clarification chooser: card with title, explanation, named lands, checkboxes, `Continuar`.
8. Composer: `OutlinedTextField` (min 3 lines, max 6) + `Enviar` icon button; label `chat_home_question_label`, placeholder `chat_home_question_hint`; character-limit error preserved; send disabled when blank.
9. Footer: privacy summary line + `Privacidad` and `Qué cubre Manijero` actions. The top-bar privacy action is the primary shortcut; the footer keeps the always-visible summary.

Message styling:
- User: `primary` container, `onPrimary` text, `You` label; rounded 16 dp, aligned to the end with a max width of 85 % of the column.
- Assistant answered: `surface` card, 1 dp `outlineVariant`, `Assistant` label, scope caption, body, source cards below.
- Abstained: `cautionSurface` card with 1 dp `caution` border, text state label `Sin respuesta segura`, body verbatim.
- Notices/working: neutral `surfaceContainerLow` card.
- Citation markers stay superscript numerals; no tappable inline links.
- Source cards: numbered chip, title, body, location, verification date, excerpt panel on `surfaceVariant`, one `Abrir documento oficial` button; excerpt never collapsed.
- Keep merge semantics exactly as today.

### 5.3 Mis terrenos — empty

```
        [olive branch illustration]
        Aún no tienes terrenos añadidos
        Añade tu primer terreno ... (plain explanation)
        [ + Añadir terreno ]   primary, full width
```

- No summary cards, no search when empty.
- Illustration decorative; heading is a real heading.
- Primary action is the only action.

### 5.4 Mis terrenos — populated

1. Title `Mis terrenos` + `land_list_description`.
2. Summary row: three cards in a responsive grid (1 column on narrow, 3 across on wide):
   - `4 terrenos guardados`.
   - `Superficie anotada`: `2,5 ha` + `2 de 4 terrenos con superficie`.
   - `Olivos anotados`: `120 olivos` + `2 de 4 terrenos con número de olivos`.
   - When no value exists: show `Sin datos` and the “0 de N” caption; never show `0 ha` as if measured.
3. Search field: leading search icon, placeholder `Buscar por nombre, municipio o tipo…`, trailing clear button with accessible label. Results update as the person types; no submit button.
4. Add action: full-width primary button `Añadir terreno` with `+` icon, placed directly under the summary (not a floating button that can cover rows). It stays reachable before the list.
5. Land rows, in repository order:
   - Name as `titleMedium`.
   - Chip row: one chip per **known** water regime, production method, and variety (for example `Secano`, `Convencional`, `Picual`).
   - Missing attributes: one secondary line listing the unknowns, for example `Sin datos: riego y variedad`. Do not repeat a bare `No lo sé` chip three times.
   - Zone line when present: `Zona: Zona alta`.
   - Measures line when present: `1,2 ha · 85 olivos`; omit each absent part.
   - Actions: `Editar` (tonal button with pencil) and `Eliminar` (danger tonal button with bin), each full-width on compact and side-by-side on wide. Accessible descriptions name the land and action.
   - Row itself is not clickable.
6. Confirmation callout after add/update/remove: check icon + message on `primaryContainer`, polite live region.
7. Load failure: danger callout + `Reintentar`; never shows an empty list.
8. Search no-results: neutral panel: `No hay terrenos que coincidan con la búsqueda.` + `Borrar la búsqueda`. The add action above the list stays reachable.
9. `Volver` at screen level is removed once tabs exist; the bottom bar is the way back.

### 5.5 Añadir terreno

Sections (all in one scroll, no collapsing that hides `No lo sé` choices):

1. **Lo esencial**
   - Name (required, single line, existing validation/focus behavior).
   - Zone or parcel (required, single line, max 80, examples in helper text).
2. **Datos opcionales** (explicitly labelled)
   - Municipality.
   - Water regime: `Secano`, `Regadío`, `Una parte de regadío y otra de secano`, `No lo sé` as large radio cards in a wrapping grid.
   - Production: `Convencional`, `Ecológico`, `Una parte de cada uno`, `No lo sé`.
   - Variety: exposed dropdown: Picual, Hojiblanca, Picudo, Lechín de Sevilla, Arbequina, Manzanilla, Gordal, Mezcla de variedades, Otra, No lo sé. When `Otra` is selected, a short free-text field appears (max 40).
   - Surface in hectares: numeric field accepting comma or dot, max two decimals, blank allowed; helper says it can stay empty.
   - Number of olive trees: whole number, blank allowed; helper says approximate is fine.
3. **Actions**
   - `Guardar terreno` primary full-width.
   - `Cancelar` text button.
   - Save failure message preserved; entered values stay.

Required-field feedback:
- Required labels read `Obligatorio` (not just a red asterisk).
- Blank name: existing message + focus return to name.
- Blank zone: `Escribe la zona o paraje del terreno.` + focus return to zone.
- Invalid surface/trees: inline plain-Spanish messages, values preserved.

### 5.6 Editar terreno

- Same form component as Añadir, prefilled.
- New records always have a zone; legacy records may not. On edit, an empty zone shows the required error on save and focuses the zone field. The land remains readable in the list until edited.
- No delete action here.
- Save success returns to the list with the update confirmation.

### 5.7 Eliminar terreno

- Title `Eliminar terreno`.
- Danger callout: land name, zone, key details, `Esta acción no se puede deshacer.`
- Primary destructive button `Eliminar el terreno` in danger colours with bin icon; `Cancelar` secondary.
- Initial focus is not on the destructive button.
- Failure/missing-land messages preserved.

### 5.8 Ayuda (Qué cubre Manijero)

- Title, intro.
- Coverage topics as a card with check/info icons and the existing topic list.
- Limits as a `caution` callout with warning icon (existing content).
- Human help as a card with plain text; privacy link.
- No FAQ accordion, no OCA directory buttons, no cooperative directory, no external links not already in content.
- `Volver` removed at screen level; the tab bar covers navigation.

### 5.9 Privacidad

- Title, intro.
- “Qué se guarda en este dispositivo” card: existing facts + new local-only fields (zone, variety, surface, tree count) explicitly named as local and not sent.
- “Qué se envía con una pregunta” card: the existing dynamic list of shared attributes; add a line that measurements and variety are never sent.
- “Qué no hacemos” and “Ayuda” cards.
- Privacy link to Ayuda retained.
- No claim of backup, sync, or verified legal status.

### 5.10 Chat states, source cards, clarification chooser

- Working: neutral card + three-dot indicator + text; `LiveRegionMode.Polite`.
- Failure: `errorContainer` callout, error border, `Reintentar`; text always says no answer exists yet.
- Abstained: caution card; state label; message verbatim; no invented next steps.
- Answered: neutral card + source cards; source excerpt always visible; external-link button with content description.
- Clarification: card with land rows (name, zone, chips) + checkboxes + `Continuar`; the local read is still the only source of land names/ids; a failed read shows the same fallback text.
- All chat surfaces keep one merged semantics node per message/row, with controls separate.

---

## 6. Component catalogue

Each component ships with light, dark, and `fontScale = 2f` previews, plus the states listed.

| Component | Responsibility | Variants / states | Key rules |
|---|---|---|---|
| `ManijeroScreen` | Shared page layout: background, scroll, padding, centred 720 dp column | compact / wide; with/without bottom inset | Replaces repeated `Surface + Column + padding` |
| `ManijeroTopAppBar` | Brand mark, title, privacy action | compact (icon + accessible label), wide (icon + visible label) | Content description; 48 dp targets |
| `ManijeroBottomNavigation` | Three destinations | selected / unselected | Label + icon + selected indicator; no colour-only state |
| `ManijeroNavigationRail` | Wide-screen destinations | selected / unselected | Labels visible; 48 dp targets |
| `ManijeroScaffold` (or direct `Scaffold`) | Insets, bar slots, content | compact / wide | One owner of insets; content never double-padded |
| `ManijeroCard` | Surface container | `surface`, `tonal`, `outlined`, `danger`; padded | 16 dp radius, 1 dp outline; no click unless given a role |
| `ManijeroSectionHeader` | Section title + optional explanation | with/without description | Optional `heading()`; no fake headings |
| `ManijeroCallout` | Inline message block | info / caution / danger / confirmation | Always icon + text; polite live region when it appears after an action |
| `ManijeroStatCard` | Summary metric | with value / without data | Caption states the denominator; never invents completeness |
| `ManijeroAttributeChip` | Land attribute | water / production / variety / neutral | Text always present; 48 dp target when interactive; non-interactive in rows |
| `ManijeroEmptyState` | Illustration + heading + body + action | lands empty | Decorative illustration; one primary action |
| `ManijeroSearchField` | Filter input | empty / text / no results | Clear button; accent-insensitive filtering in the pure function, not in the UI |
| `ManijeroChoiceCard` | Radio/segmented choice | selected / unselected / error | `selectableGroup`, `Role.RadioButton`, large target, `No lo sé` never hidden |
| `ManijeroDropdownField` | Variety selection | closed / open / error / custom | Exposed dropdown; keyboard and screen-reader support |
| `ManijeroMeasureField` | Numeric optional input | empty / valid / invalid | Decimal comma/dot; helper text; no inference |
| `ManijeroPrimaryButton` | Filled action | enabled / disabled | 48 dp height; icon + text; one primary action per region |
| `ManijeroSecondaryButton` | Outlined/tonal action | enabled / disabled | Used for cancel/back/secondary |
| `ManijeroDangerButton` | Destructive action | enabled / disabled | Danger colours + bin icon + explicit label |
| `ManijeroBrandMark` | Identity vector | light/dark | Decorative; the visible title carries the app name |
| `ManijeroOliveBranch` | Empty-state illustration | light/dark | `contentDescription = null` |
| `ManijeroIcon` | Vector icon wrapper | size/tint/description | 24 dp default; decorative unless given a description |
| `ChatBubble` | User/assistant transcript card | user / assistant / notice / abstained | One merged semantics node; scope/state labels |
| `ChatComposer` | Question input + send | empty / text / over limit / sending | Send button label; preserve text on failure |
| `SuggestedQuestionChips` | Example prompts | wrapped / large text | Chips wrap; selection fills the question field as today |
| `SourceCardView` | Cited source | openable / unavailable | Number, title, body, date, excerpt, one open action |
| `ClarificationChooser` | Choose lands | loading local read / no lands / rows / selected | Filtered to returned ids; never fabricates a land |
| `LandRow` | Saved land | known/unknown attributes; long text | Not clickable; two labelled actions |
| `LandForm` | Shared add/edit form | add / edit / legacy zone / errors | Same field order and validation in both |
| `RemoveLandConfirmation` | Delete confirmation | normal / failure / missing | Danger callout; cancel first focus |
| `InfoCard` | Help/privacy sections | info / caution | Used by Ayuda and Privacidad |

Implementation notes:
- Do not wrap every Material 3 control one-to-one. Create a component only where it standardises behavior, semantics, or repeated styling.
- Keep component files under `shared/src/commonMain/kotlin/com/jamarglex/manijero/design/` (new package) except chat-specific ones, which stay in `chat/`, and land-specific ones in `lands/`.
- All previews use `ManijeroTheme`; no screen defines its own palette.

---

## 7. Data and content changes

### 7.1 Land model

```kotlin
data class Land(
    val id: String,
    val name: String,
    val zone: String? = null,            // required for new/edited records; null only for legacy rows
    val municipality: String? = null,
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val variety: LandVariety = LandVariety.UNKNOWN,
    val varietyOther: String? = null,    // only when variety == OTHER
    val areaHectares: Double? = null,    // already persisted; now collected
    val treeCount: Int? = null,
    val notes: String? = null,           // remains hidden and unsent
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
)

enum class LandVariety {
    UNKNOWN, PICUAL, HOJIBLANCA, PICUDO, LECHIN_DE_SEVILLA,
    ARBEQUINA, MANZANILLA, GORDAL, MIXED, OTHER,
}
```

- `LandDraft` gains `zone`, `variety`, `varietyOther`, `treeCount`; `areaHectares` is now exposed.
- `zone` is required in the form/reducer, not in the storage decoder (legacy records must load).
- No changes to `MinimalLandContext`, `AskRequest`, OpenAPI, backend, or the chat payload.
- `notes` stays hidden; do not turn it into zone. Zone is its own field with its own meaning and copy.

### 7.2 Store format

- Keep `land-store-v1` files readable. Write a new `land-store-v2` header with fields:
  `id | name | zone | municipality | waterRegime | productionMethod | variety | varietyOther | areaHectares | treeCount | notes | createdAt | updatedAt`.
- Decoder accepts both headers: v1 (9 fields) maps missing fields to `null`/`UNKNOWN`; v2 requires its field count.
- Writer emits v2 only.
- Escaping stays the same (`%`, `|`, newline, carriage return).
- Corrupt/unknown records keep the current conservative behavior: skip the record, never invent values.
- Add fixtures for: v1 file, v2 file, mixed file, escaped zone/variety text, invalid enum, invalid numbers, empty file.
- Desktop file name: keep `lands-v1.txt` (path compatibility) even though contents are v2; document it. Do not rename user data.
- Downgrade is not supported: an older build cannot read a v2 file. Record this limitation in the spec; do not claim backup or rollback.

### 7.3 Validation and normalization

| Field | Rule | Error copy (Spanish) |
|---|---|---|
| Name | Trimmed, non-blank | `Escribe un nombre para el terreno.` |
| Zone | Trimmed, non-blank, max 80 | `Escribe la zona o paraje del terreno.` |
| Municipality | Optional, trim, blank → null | — |
| Variety | Enum; `OTHER` requires non-blank `varietyOther` max 40 | `Escribe la variedad del terreno.` |
| Surface | Optional, ≥ 0; comma or dot accepted; more than two decimals rounded to two on save | `Escribe una superficie válida, por ejemplo 1,5.` |
| Trees | Optional, whole number ≥ 1 | `Escribe un número de olivos válido.` |
| Water/production | Enum incl. `UNKNOWN` | — |

- Never infer surface from tree count or vice versa.
- Never require surface/trees/variety.
- `zone` required only for new/edited records; legacy rows remain valid.

### 7.4 Summary calculations

Pure, tested functions:

```kotlin
data class LandSummary(
    val total: Int,
    val surfaceTotal: Double?,   // null when no land has a value
    val surfaceKnownCount: Int,
    val treeTotal: Int?,         // null when no land has a value
    val treeKnownCount: Int,
)
```

- `surfaceTotal` sums only known values; `surfaceKnownCount` drives the caption.
- Format hectares in `commonMain` without JVM-only APIs: up to two decimals, comma separator, trailing zeros trimmed (`1,5`, `2`, `0,75`). Add unit tests for rounding and long decimals.
- Tree totals are integers; format with no separators for small values, and a plain space for thousands if needed (`1 200`), tested.
- Copy: `Superficie anotada` + `2 de 4 terrenos con superficie`; never “superficie total”.
- If `surfaceKnownCount == 0`, show `Sin datos` and `0 de N terrenos con superficie`.

### 7.5 Search

Pure function:

```kotlin
fun filterLands(lands: List<Land>, query: String): List<Land>
```

- Fold case and Spanish diacritics (`á é í ó ú ü ñ`) for both query and searchable fields.
- Searchable: name, municipality, zone, variety label (including `Otra` custom text), water-regime label, production-method label.
- Do not search ids, notes, timestamps, or numeric measures.
- Empty/blank query returns the original list unchanged.
- Preserve repository order; no ranking.
- Tests: accents, ñ, uppercase, emoji, punctuation, multiple words, blank, no match.

### 7.6 Privacy and chat boundary

- Update `land_data_disclosure` facts and `PrivacyScreen` copy:
  - Local-only: zone, variety, surface, tree count, plus existing name, municipality, full record.
  - Sent only when needed: municipality, water regime, production method, opaque id.
  - Never sent: name, zone, variety, surface, tree count, notes.
- Add a test asserting a serialized `AskRequest` for a land with all new fields never contains zone/variety/varietyOther/area/treeCount.
- No log line may include land names, zones, or new fields.

### 7.7 Copy inventory (new or changed keys)

| Key area | Examples |
|---|---|
| Navigation | `nav_assistant`, `nav_lands`, `nav_help`, `nav_privacy` |
| Summary | `land_summary_count`, `land_summary_surface`, `land_summary_trees`, `land_summary_surface_caption`, `land_summary_trees_caption`, `land_summary_no_data` |
| Search | `land_search_label`, `land_search_hint`, `land_search_clear`, `land_search_no_results` |
| Land fields | `add_land_zone_label`, `add_land_zone_help`, `add_land_zone_error`, `add_land_variety_label`, `add_land_variety_other`, `add_land_variety_mixed`, `add_land_surface_label`, `add_land_surface_help`, `add_land_surface_error`, `add_land_trees_label`, `add_land_trees_help`, `add_land_trees_error`, `add_land_required` |
| Land list | `land_list_zone`, `land_list_variety`, `land_list_measures_surface`, `land_list_measures_trees`, `land_list_missing_attributes` (`Sin datos: %1$s`), `land_attribute_water`, `land_attribute_production`, `land_attribute_variety` |
| Privacy | local-only field lines; “not sent” line |
| Empty state | existing `land_list_empty` + new heading/body keys if copy changes |

All new keys need plain-Spanish review and large-text previews.

---

## 8. Work breakdown

Estimates are sessions of focused work, not calendar dates. Each step ends with the listed check; the feature as a whole also gets its spec, appendix, and validation record.

### Phase 0 — Design foundation

| Step | Work | Files | Done when |
|---|---|---|---|
| P0-01 | Inventory raw colours, ad-hoc shapes, duplicated screen padding, one-to-one wrappers to avoid | read-only audit note in the spec appendix | List is complete; no code changed |
| P0-02 | Apply the Stitch light palette verbatim (plus the corrected `outlineVariant`) and the semantic colours | `theme/ManijeroColors.kt` | Theme compiles; no hex outside the file |
| P0-03 | Apply the Stitch dark palette verbatim (plus the corrected `outlineVariant`) | `theme/ManijeroColors.kt` | Dark previews match the Stitch roles; no derived roles remain |
| P0-04 | Extend shape/spacing/icon-size/density tokens | `theme/ManijeroTokens.kt` | New tokens used by components; no magic numbers in screens |
| P0-05 | Update contrast tests with every role pair, chip pair, caution pair, and boundary pair | `commonTest/theme/ManijeroColorsTest.kt` | All listed pairs pass; failures block |
| P0-06 | Update design-system tests and token previews | `commonTest/theme/ManijeroDesignSystemTest.kt`, `theme/ManijeroTheme.kt` | Light/dark/large-text token board passes |
| P0-07 | Draw the brand mark vector | `composeResources/drawable/brand_mark.xml` | Renders at 28/32/48 dp; no blur; dark/light contrast checked |
| P0-08 | Draw the olive-branch empty-state vector | `composeResources/drawable/olive_branch.xml` | Decorative semantics; scales 160–200 dp |
| P0-09 | Draw the 16 UI icon vectors | `composeResources/drawable/ic_*.xml` | 24 dp grid, 2 dp stroke, consistent joins |
| P0-10 | Add `ManijeroIcon` + `ManijeroBrandMark` + `ManijeroOliveBranch` wrappers | `design/` | Wrappers expose size/tint/description; previews cover both themes |
| P0-11 | Build `ManijeroScreen`, `ManijeroCard`, `ManijeroSectionHeader` | `design/` | Reused by at least two screens; previews |
| P0-12 | Build `ManijeroCallout`, `ManijeroStatCard`, `ManijeroEmptyState` | `design/` | All tones and empty states previewed |
| P0-13 | Build `ManijeroAttributeChip`, `ManijeroChoiceCard` | `design/` | Text always present; 48 dp targets; error state |
| P0-14 | Build `ManijeroSearchField`, `ManijeroDropdownField`, `ManijeroMeasureField` | `design/` | Keyboard, clear, error, large-text previews |
| P0-15 | Build `ManijeroTopAppBar`, `ManijeroBottomNavigation`, `ManijeroNavigationRail` | `design/navigation/` | Selected state not colour-only; 48 dp targets |
| P0-16 | Add the preview gallery (preview-only, not a shipped route) | `design/ComponentGallery.kt` | One place to inspect all components in light/dark/2× text |
| P0-17 | Add `Scaffold` shell, insets, tab state, back rules | `App.kt`, `design/` | Tabs switch; Android back works; state survives tab switch |
| P0-18 | Replace top-level destination text buttons with the tab shell; keep form back | `App.kt` | No duplicate top-level “Volver”; forms still cancel/back |
| P0-19 | Shell tests and previews (compact/wide, light/dark, 2× text) | `commonTest`, previews | Pure navigation mapping tested; no UI harness claimed |

### Phase 1 — Land data and content

| Step | Work | Files | Done when |
|---|---|---|---|
| P1-01 | Append the superseding field decision and create the new owning spec; note affected contracts without rewriting past acceptance records | `docs/specs/land_setup_fields_decision.md` (append only), new `docs/specs/land_measurement_fields.md`, owner-spec notes | Scope change explicit, evidence gap stated, no code changed |
| P1-01b | Update `DESIGN.md` field and privacy guidance only after approval of the new spec | `DESIGN.md` | Design guidance matches the approved fields |
| P1-02 | Add `zone`, `variety`, `varietyOther`, `treeCount` to model/draft | `lands/Land.kt` | Compiles; defaults preserve old call sites |
| P1-03 | Add v2 store encode/decode with v1 compatibility | `lands/LandRepository.kt` | v1/v2 fixtures pass; escaped text round-trips |
| P1-04 | Normalize/validate new fields in the repository | `lands/LandRepository.kt` | Invalid records never written; tests |
| P1-05 | Extend add/edit reducers with field state and validation | `lands/AddLandState.kt`, `EditLandState.kt` | Blank zone/variety-other/invalid numbers rejected with focus target |
| P1-06 | Extend draft mapping and edit prefill | `lands/*State.kt`, `App.kt` | Values survive save failure; legacy zone stays empty |
| P1-07 | Add the new fields to the add form | `lands/AddLandScreen.kt` | Required/optional copy; previews |
| P1-08 | Reuse the form in edit with prefill and legacy-zone path | `lands/EditLandScreen.kt` | Editing a legacy land requires zone; list remains readable |
| P1-09 | Show zone/variety/measures/chips in land rows and clarification chooser | `lands/LandListScreen.kt`, `App.kt` | Only known values shown; no inferred value |
| P1-10 | Implement `LandSummary` derivation + number formatting | new `lands/LandSummary.kt` | Unit tests: empty, partial, all known, rounding |
| P1-11 | Implement `filterLands` | new `lands/LandSearch.kt` | Unit tests: accents, ñ, case, emoji, blank, no match |
| P1-12 | Add summary cards + search UI to the list | `lands/LandListScreen.kt` | Partial captions correct; no-results state |
| P1-13 | Add empty-state illustration + copy | `lands/LandListScreen.kt` | One primary action; decorative illustration |
| P1-14 | Update privacy copy and disclosure facts | `privacy/*`, `strings.xml` | Local-only vs sent is explicit; tests |
| P1-15 | Assert new fields never enter the `/ask` payload | `commonTest/chat/LandContextBuilderTest.kt` | Serialized request contains none of the new fields |
| P1-16 | Update the feature's evidence and validation records after verification | new feature appendix/validation, `PROGRESS.md` | Evidence recorded; no earlier acceptance record rewritten |

### Phase 2 — Screen adaptation

| Step | Work | Files | Done when |
|---|---|---|---|
| P2-01 | Chat hero + title/description block | `App.kt` / `chat/` | No “verified/official” affordance |
| P2-02 | Chat message cards (user/assistant/abstention/notice) | `chat/` | Semantics preserved; contrast verified |
| P2-03 | Suggested-question chips | `chat/` | Wrap at 2× text; same actions |
| P2-04 | Composer + send button + character limit | `chat/` | Send disabled when blank; error preserved |
| P2-05 | Working/failure states as callouts | `chat/` | Live regions; retry works |
| P2-06 | Source cards restyle | `chat/` | Excerpt visible; open action labelled |
| P2-07 | Clarification chooser restyle + zone/chips | `chat/` | Loading/no-lands/rows states; no fabricated land |
| P2-08 | Chat footer privacy/help actions | `chat/` | Summary always visible; links labelled |
| P2-09 | Lands header + summary + search + add CTA | `lands/LandListScreen.kt` | Empty/populated/search-no-results distinct |
| P2-10 | Land rows + tonal edit/delete actions | `lands/LandListScreen.kt` | 48 dp actions; not clickable row |
| P2-11 | Lands confirmations/load failure | `lands/LandListScreen.kt` | Polite live region; retry |
| P2-12 | Add screen layout and field grouping | `lands/AddLandScreen.kt` | One scroll; no hidden `No lo sé` |
| P2-13 | Edit screen layout | `lands/EditLandScreen.kt` | Same order; legacy path |
| P2-14 | Remove screen danger treatment | `lands/RemoveLandScreen.kt` | Cancel-safe default focus |
| P2-15 | Ayuda screen cards + limits callout | `coverage/CoverageScreen.kt` | Same content; no new links |
| P2-16 | Privacidad screen cards + local-only section | `privacy/PrivacyScreen.kt` | Copy matches disclosure facts |
| P2-17 | Wide Desktop pass per screen | `design/`, screens | Rail + centred column; no stretched phone layout |
| P2-18 | Dark pass per screen | all screens | Every state previewed dark and observed |
| P2-19 | Large-text pass per screen | all screens | 2× text, 320 dp width: no clipping, no hidden actions |
| P2-20 | Keyboard/focus/screen-reader pass per screen | all screens | Focus order documented; labels announced; destructive action not auto-focused |

### Phase 3 — Verification and documentation

| Step | Work | Done when |
|---|---|---|
| P3-01 | Run contrast and design-system tests | Green |
| P3-02 | Run `./scripts/init.sh --fast` | Green (pytest caveat unchanged) |
| P3-03 | Run `./scripts/init.sh --verify` | Green |
| P3-04 | Android emulator: light/dark, 320/compact/wide, 2× text screenshots | Evidence stored in the feature's appendix/validation |
| P3-05 | Desktop: light/dark, 800×600 and 1280×800 screenshots | Evidence stored |
| P3-06 | iOS simulator compile smoke (if toolchain available) | Compiles or limitation recorded |
| P3-07 | Confirm `DESIGN.md` matches the implemented palette, and add components, chrome, fields, copy rules | Document matches implementation |
| P3-08 | Update `design-references/README.md` mapping and dark status | No stale “dark unverified” claim |
| P3-09 | Update specs/validations/`feature_list.json`/`PROGRESS.md`/session log after validation | Repo workflow satisfied |
| P3-10 | Manual low-digital-confidence check (owner `chat_accessibility`) | Observations recorded, or remains explicitly outstanding |

---

## 9. Feature slicing and sequencing

Only after your approval, add these entries to `feature_list.json` with specs and appendices:

| Proposed feature | Steps | Depends on | Kind |
|---|---|---|---|
| `design_token_refresh` | P0-01…P0-06 | — | Visual foundation |
| `brand_vectors` | P0-07…P0-10 | `design_token_refresh` | Visual foundation |
| `ui_component_library` | P0-11…P0-16 | `brand_vectors` | Visual foundation |
| `app_chrome_navigation` | P0-17…P0-19 | `ui_component_library` | Behaviour/structure change |
| `land_measurement_fields` | P1-01…P1-09, P1-14…P1-16 | `design_token_refresh`, `ui_component_library` | Data + product change |
| `land_search_and_summary` | P1-10…P1-13 | `land_measurement_fields` | Product addition |
| `chat_screen_refresh` | P2-01…P2-08 | `app_chrome_navigation`, `ui_component_library` | Visual adaptation |
| `lands_screens_refresh` | P2-09…P2-14 | `app_chrome_navigation`, `land_search_and_summary` | Visual adaptation |
| `help_privacy_refresh` | P2-15…P2-16 | `ui_component_library`, `land_measurement_fields` | Visual adaptation + copy |
| `ui_refresh_accessibility_audit` | P2-17…P2-20, P3-01…P3-10 | all above | Verification |

Sequencing rule: finish and validate each feature before starting the next. `design_token_refresh` and the pure data layer (`Land.kt`, store format, summary/search functions) touch disjoint files and are the only safe parallel lane; everything else is serial to keep review and evidence honest.

Why this order:
- Palette and components first, so screens are adapted once.
- Navigation before screens, so every screen is laid out inside the final shell.
- Fields before lands screens, so the list/form are built once with their final content.
- Chat before or after lands is independent once the shell exists; chat is higher risk (semantics, live regions), so do it before the larger lands restyle to keep review focused.

Registration: `design_token_refresh` was added to `feature_list.json` on 2026-10-25 with
[`docs/specs/design_token_refresh.md`](../specs/design_token_refresh.md) and its appendix; the remaining
entries are registered one at a time, each when its spec is planned.

---

## 10. Verification and evidence

### 10.1 Commands

| Tier | Command | Use |
|---|---|---|
| Focused | `./scripts/init.sh --feature <feature-id>` | Per feature |
| No-device | `./scripts/init.sh --fast` | Shared JVM tests, contracts, backend tests, evaluators |
| Full | `./scripts/init.sh --verify` | Adds Android host tests, APK, Desktop build |
| Android | `./scripts/init.sh --android-run` | Emulator evidence |
| Desktop | `./scripts/init.sh --desktop` | Desktop evidence |
| iOS smoke | `./gradlew :shared:compileKotlinIosSimulatorArm64` (verify the exact task name) | Shared-code compatibility only |

### 10.2 Evidence required per feature

- Unit tests for every pure function (summary, search, store format, field validation, navigation mapping).
- Contrast tests covering the approved pair list, including chips and dark mode.
- Previews for every component state and every screen state, light/dark/2× text.
- Android and Desktop screenshots for the screens the feature touches.
- A short manual accessibility note: focus order, screen-reader labels, 48 dp targets, 2× text behavior.
- An explicit “not verified” line for anything the repo cannot verify (iOS runtime, real users, automated UI/E2E).

### 10.3 What this plan does not prove

- It does not prove legal coverage, answer quality, or backend behavior; those are unchanged.
- It does not prove usability with low-digital-confidence users. The manual check stays outstanding.
- It does not prove iOS rendering; only shared-code compatibility.
- It does not establish that the new fields improve answers; they are local context for the person, not legal evidence.

---

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Required zone blocks low-confidence users or contradicts the accepted field decision | Explicit decision record; plain helper text with examples; legacy lands remain valid; manual comprehension check; revisit if users stall |
| Partial totals mislead (“2,5 ha” looks complete) | Caption always states the denominator; `Sin datos` when none; never label “total” |
| Palette changes break contrast | Pre-computed pairs plus mandatory tests; fallback to the accepted values for any failing pair |
| Dark mode has leaked blue/off-family roles | Correct tertiary; test every role; dark screenshots per screen |
| Navigation refactor loses chat state or breaks back | Hoist state; pure navigation mapping tests; Android back manual check; no deep links |
| `App.kt` extraction causes conflicts or regressions | Extract in small steps inside the owning feature; keep behavior identical; test after each |
| New fields leak to `/ask` or logs | Explicit serialization test; disclosure copy; no logging of field values |
| Store v2 breaks existing desktop data | v1 fixtures, mixed-file fixtures, conservative skipping, keep the same file path |
| Hand-authored icons look inconsistent | One 24 dp grid, 2 dp stroke, shared wrapper, visual QA in the gallery |
| Search fails on accents/ñ | Pure fold function with a dedicated test set |
| Scope creep from mockup content | Non-goals list; review gate; new content needs a spec |
| Large-text layouts clip chips/actions | 2× previews per component and per screen; wrapping grids |
| No automated UI harness | Manual screenshot evidence; never claim more than observed |
| iOS drift | Keep `commonMain` pure; optional compile smoke; no iOS-only APIs |

---

## 12. Open decisions for review

Palette values were decided on 2026-10-25: the Stitch token block wins verbatim, with two gated `outlineVariant` corrections (§3.1). The remaining items are open; each shows the recommended choice.

1. **Palette values** in §3.1 — **decided 2026-10-25**: Stitch token block adopted, `outlineVariant` corrected in both modes, recorded in `DESIGN.md`; no further approval needed.
2. **Top-bar right action** — privacy (proposed) versus no action versus help.
3. **Add CTA position** — directly under the summary (proposed) versus a sticky bottom button/FAB.
4. **Legacy lands without zone** — omit zone in the list and require it only when editing (proposed) versus show a “falta la zona” note.
5. **Search scope** — exclude numeric measures (proposed); include them if you expect people to search “1,5”.
6. **“Otra” variety** — require a short free-text value (proposed) or allow the label alone.
7. **Variety shortlist** — confirm Picual, Hojiblanca, Picudo, Lechín de Sevilla, Arbequina, Manzanilla, Gordal; add/remove any.
8. **Summary wording** — `Superficie anotada` / `Olivos anotados` (proposed) versus alternative plain-Spanish labels.
9. **Zone in the clarification chooser** — show it to distinguish lands (proposed) or keep only name + existing attributes.
10. **Desktop default/minimum window size** — set 1100×800 / minimum 720×600 (proposed) or leave platform default.
11. **Launcher icon** — keep the stock template for now (proposed; separate polish feature).
12. **Motion** — minimal fades only (proposed) or no animation at all.

---

## 13. Review checklist

- [ ] The confirmed decisions in §1 match your intent.
- [x] The palette is decided (2026-10-25): Stitch token values verbatim, plus the two `outlineVariant` corrections, recorded in `DESIGN.md`.
- [ ] Keeping Material 3 typography is still the right trade-off after seeing the target.
- [ ] The three-tab chrome and privacy action are right for low-confidence users.
- [ ] The required-zone decision and its scope-change record are acceptable.
- [ ] The field list and validation rules in §7 are complete and correctly scoped.
- [ ] Search and summary behavior is what you expect.
- [ ] No mockup content you wanted has been left out of scope.
- [ ] The feature slicing in §9 is the order you want to execute.
- [ ] The verification plan is sufficient and honest.
- [ ] The open decisions in §12 are answered or delegated.

After approval, the next action is to create the first feature spec (`design_token_refresh`) and its appendix through the normal feature-spec workflow; no code is written before that spec is reviewed.

---

## Appendix A — File map (expected)

| Area | New | Modified |
|---|---|---|
| Theme | — | `theme/ManijeroColors.kt`, `theme/ManijeroTheme.kt`, `theme/ManijeroTokens.kt` |
| Design system | `design/ManijeroScreen.kt`, `design/ManijeroCard.kt`, `design/ManijeroCallout.kt`, `design/ManijeroStatCard.kt`, `design/ManijeroEmptyState.kt`, `design/ManijeroChip.kt`, `design/ManijeroChoiceCard.kt`, `design/ManijeroFields.kt`, `design/ManijeroButtons.kt`, `design/ManijeroIcon.kt`, `design/ManijeroBrandMark.kt`, `design/ManijeroOliveBranch.kt`, `design/navigation/*`, `design/ComponentGallery.kt` | — |
| Resources | `composeResources/drawable/brand_mark.xml`, `olive_branch.xml`, `ic_*.xml` | `composeResources/values/strings.xml` |
| Shell | — | `App.kt` (composition root + shell only) |
| Chat | `chat/ChatComposer.kt`, `chat/ChatMessages.kt`, `chat/SourceCards.kt`, `chat/ClarificationChooser.kt`, `chat/ChatStates.kt` | `App.kt`, `chat/*` |
| Lands | `lands/LandSummary.kt`, `lands/LandSearch.kt`, `lands/LandForm.kt`, `lands/LandRow.kt` | `lands/*.kt`, `App.kt` |
| Privacy/help | `design/InfoCard.kt` | `privacy/PrivacyScreen.kt`, `coverage/CoverageScreen.kt`, `privacy/LandDataDisclosure.kt` |
| Tests | `commonTest/lands/LandSummaryTest.kt`, `LandSearchTest.kt`, `LandStoreFormatV2Test.kt`, `commonTest/design/*` | `ManijeroColorsTest.kt`, `ManijeroDesignSystemTest.kt`, `AddLandStateTest.kt`, `EditLandStateTest.kt`, `LandRepositoryTest.kt`, `LandContextBuilderTest.kt`, `LandDataDisclosureTest.kt` |
| Docs | this plan | `DESIGN.md`, `design-references/README.md`, owner specs/validations, `feature_list.json`, `PROGRESS.md`, session log |

## Appendix B — Screen × state matrix

| Screen | Light | Dark | 320 dp | Wide | 2× text | Error | Empty | Loading |
|---|---|---|---|---|---|---|---|---|
| Asistente | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Mis terrenos | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | n/a (local read) |
| Añadir | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a |
| Editar | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a |
| Eliminar | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a |
| Ayuda | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a | n/a |
| Privacidad | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a | n/a |
| Clarification | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Source card | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a |

## Appendix C — Copy samples for review

```text
Tabs: Asistente · Mis terrenos · Ayuda
Summary: 4 terrenos guardados · Superficie anotada: 2,5 ha (2 de 4) · Olivos anotados: 120 (2 de 4)
Search: Buscar por nombre, municipio o tipo…
No results: No hay terrenos que coincidan con la búsqueda.
Missing attributes: Sin datos: riego y variedad
Zone: Zona o paraje — Obligatorio
Zone help: Por ejemplo, «Zona alta» o «Cerca del pozo».
Variety: Variedad — Opcional
Variety options: Picual · Hojiblanca · Picudo · Lechín de Sevilla · Arbequina · Manzanilla · Gordal · Mezcla de variedades · Otra · No lo sé
Surface: Superficie (hectáreas) — Opcional. Si no la sabes, déjala vacía.
Trees: Número de olivos — Opcional. Un número aproximado es suficiente.
Remove: Vas a eliminar «Los Olivos». Esta acción no se puede deshacer.
Privacy: La zona, la variedad, la superficie y el número de olivos se guardan solo en este dispositivo y no se envían con tus preguntas.
```
