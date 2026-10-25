# Validation — `chat_screen_refresh`

## Verdict

**Accept** — 2026-10-25. Independent review of the implementation against
[`docs/specs/chat_screen_refresh.md`](../specs/chat_screen_refresh.md).

Feature id: `chat_screen_refresh`. Claimed status before validation: `passing`.
The validator recommends setting it to `accepted` and recording this acceptance in
`PROGRESS.md` and `docs/progress/session-log.md`.

The validation session re-read the contract, implementation, evidence, docs and changed image set;
it did not make product-code changes. The validator workflow's secondary agent could not start
because the session budget was exhausted, so this record is based on direct review and independently
re-run local gates rather than a second-agent report.

## Review target

Commit reviewed: `302581c feat: complete chat_screen_refresh`, based on planning commit `7759b83`.
The change contains the six chat UI files, the permanent Desktop interaction test, fixture and host
screenshot changes, ten intentionally replaced goldens, four new chat goldens and the required
durable documentation. `git diff --check` is clean. No change was found in chat domain/state,
`design/`, `theme/`, drawables, shell/navigation, backend, contracts, knowledge, or Gradle files.

## Independent checks and results

Re-run from the feature worktree:

- `./scripts/init.sh --feature chat_screen_refresh` → exit 0; the three interaction tests and both
  host screenshot suites pass; the spec's extraction, import, copy, drawable, inventory and scope
  gates pass.
- `./scripts/init.sh --fast` → exit 0, `Fast tier passed` (all nine offline checks).
- `./scripts/init.sh --verify` → exit 0; fast tier plus Android host tests, Android debug assembly
  and Desktop build pass.
- `./gradlew :shared:compileKotlinIosSimulatorArm64` → `BUILD SUCCESSFUL`.
- `git diff --check` → clean.
- Screenshot inventory: Desktop has 22 images and Android has 18; the chat subset is 6 Desktop / 4
  Android, including `chat_abstention_dark` and `chat_clarification_light` on both hosts. The ten
  changed existing images are exactly the six Desktop and four Android chat/shell images listed in
  the appendix. No unrelated image is changed.
- Opened the changed and added Desktop/Android PNGs at full size. The hero, speaker contrast,
  citation/source treatment, caution abstention and chooser render as documented. The chooser
  checkbox is aligned beside its land name. Temporary 2× Desktop frames were also rendered,
  inspected and removed; the suggestion questions wrap in full, and the chooser details wrap and
  remain scrollable.

## Spec conformance

All twelve acceptance scenarios are satisfied by code, the interaction tests, host goldens and the
recorded temporary 2× review. In particular:

- `ChatHomeScreen` retains its signature and is in the existing `chat/` package; `App.kt` is a
  composition root and has no chat composable, preview or sample block.
- The shared screen frame and stacked tonal hero use the accepted design components and tokens.
- Transcript labels, merging, polite regions, user/assistant visual distinction, caution state,
  citations and source cards are preserved by inspection and image review.
- Suggested-question callback behavior and blank-send/retry interaction behavior are proven by the
  permanent three-test `ChatHomeInteractionTest`.
- The chooser retains guarded unresolved/empty/filtered-list branches and its selection callback;
  no domain, request, payload or land-store behavior changed.
- No new visible string or drawable was added; `chat_home_submitted` is the only removed string.
- Screenshot docs report 22 Desktop / 18 Android captures and retain the host-render limitations.

### Accepted deviations and limits

- **Stacked hero:** the mark sits above the heading, not beside it. Full-size 2× shell review showed
  the side-by-side layout forcing the final question mark onto a separate line. The stacked layout
  preserves the single heading and the full-width title column.
- **Chooser checkbox position:** the visual box is offset upward by the shared small spacing token so
  it appears beside the selected land's name, not halfway down its multi-line details. The full
  Material target, row toggle semantics and 12 dp row padding remain.
- The working notice is static text rather than animated dots; the composer uses a visible
  `Preguntar` label rather than an icon-only `Enviar` button. Both decisions are in the planning
  record and durable docs.
- At compact shell size the send button is below the initial 360×800 dp viewport and requires a
  short scroll; the field and button remain in the same page scroll. This is explicitly documented
  for product-owner review, not represented as a hidden or absent control.
- At 2× the compact bottom navigation labels wrap/clip, an accepted shell limitation not introduced
  by this change. Desktop images are macOS-font-pinned; Android images are Robolectric host renders.

## Security assessment

Feature-scoped review found no relevant blocking issue. The change is presentational: no new request,
endpoint, persistence, permission, logging, personal-data flow, or dependency. The chooser continues
to filter the supplied local lands by the service-provided opaque ids. Source links use the existing
best-effort URI handler under `runCatching`; the wire contract and legal-answer behavior are
unchanged.

## Documentation / harness state

`DESIGN.md`, `CONSTRAINTS.md`, `docs/screenshot-regression.md`, the refresh plan delivery note, the
risks register and the feature appendix reflect the shipped behavior and its limits. The focused
spec block ran successfully. The feature was `passing` before independent validation; acceptance
state and progress pointers are left to the orchestrator.

## Non-blocking findings and unperformed checks

- No emulator smoke (`--android-run`), interactive Desktop smoke (`--desktop`), TalkBack/VoiceOver
  or keyboard traversal, real device/tablet/OS matrix, iOS runtime, low-digital-confidence user
  session, or product-owner image sign-off was run. These remain manual checks and are not implied by
  host goldens or this acceptance.
- The compact shell requires scrolling to reach `Preguntar`; confirm this cost with the owner before
  release. It is documented in `DESIGN.md`, the appendix and the risks register.

No blocking or required revision findings.
