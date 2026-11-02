# Validation: welcome_first_use

- Verdict: **accept** (independent validator, 2026-11-02). Owner decision: validator accept is final; no owner walkthrough.
- Spec: [welcome_first_use.md](../specs/welcome_first_use.md) · Evidence: [appendix](../specs/welcome_first_use.appendix.md)

## Checks rerun
- `./scripts/init.sh --feature welcome_first_use`: passed (all five published commands; goldens verified).
- `./scripts/init.sh --fast`: passed (9 checks; backend 1716 passed, 4 skipped).
- `./scripts/init.sh --verify`: passed (Android host tests, Android and Desktop builds).

## Spec review
- Copy: the seven new keys in `strings.xml` are additions only and match the copy table verbatim.
- Copy trace: every sentence reuses accepted wording or its facts.
  - `welcome_can` is `coverage_intro` verbatim.
  - `welcome_limits` condenses `coverage_no_personal`, `coverage_no_coop` and `coverage_help_body`.
  - `welcome_privacy` is `chat_home_privacy_summary` plus the first sentence of `privacy_promise_body_2`.
  - `welcome_lands` is the second sentence of `chat_home_description` plus the pinned Ayuda pointer.
  - No digit, contact detail, deadline, amount or promise. `WelcomeCopyGuardTest` enforces this.
- Behaviour:
  - Card is before the hero, with one outlined `Entendido`, a `titleMedium` title and no heading semantics.
  - `Ver bienvenida` shows only when a store is injected, via `showAgain()`, Assistant section and Chat destination.
  - Unreadable store shows the card. A refused write still hides it. Nothing is logged.
  - Android uses `manijero_welcome` prefs with synchronous `commit()`; Desktop uses `~/.manijero/welcome-v1.txt`.
  - Both hosts inject the store unconditionally.
- Scope: `AppNavigation.kt`, existing strings and existing goldens are unchanged. Only 4 new PNGs were added.
- Docs: ARCHITECTURE, client-chat constraint, DESIGN and screenshot-regression are updated as listed.

## Security / privacy
No findings. The flag is one boolean, device-local, never sent or logged.

## Limits that remain
- No usability, screen-reader or on-device evidence (`usability_session`).
- iOS has no store, so it shows no card.
- Dismissal is not shown again after a restart; the card shows until dismissed, not once.
