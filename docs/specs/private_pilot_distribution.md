# Feature Spec: `private_pilot_distribution`

## Source metadata

- **Feature:** `private_pilot_distribution` — Distribute private Android and Desktop pilot builds (`release`).
- **Status at planning:** `not_started`; depends on accepted Android/Desktop builds, `hosted_pilot_operations`, and `pilot_privacy_readiness`.
- **Source behavior:** The owner provides private direct links to a release APK and macOS Desktop installer for the approved pilot.
- **Feature-list verification:** Artifacts are built from a recorded revision, installed/launched on the declared platforms, contain the reviewed hosted API URL, and are available only through the chosen private distribution path.
- **Feature-list note:** Pilot targets are Android and macOS only. Windows/Linux and public stores are out of scope.

## Goal and boundaries

Prepare a small private distribution for invited pilot participants: Android APK and macOS Desktop installer shared through private direct links. Builds must point to the approved hosted service and carry truthful privacy/help information.

**In scope:** release build configuration, reproducible artifacts, version/revision records, integrity hashes, private link access control and expiry, install/upgrade instructions, and a way to revoke access to future downloads.

**Non-goals:** Google Play/App Store publication, public GitHub releases, Windows/Linux installers, iOS, auto-update, broad user onboarding research, or claiming signed/notarized distribution until that work is verified.

## Job story

When the owner invites someone to the private pilot, they want to share a build that connects to the reviewed service and can be installed on the agreed platform, so participants can use the app without a public release.

## Acceptance scenarios

### Android pilot build

Given an approved release revision and hosted API URL, when the APK is built, then it installs and launches on the declared Android test device and uses HTTPS to reach the reviewed API.

### macOS Desktop pilot build

Given an approved release revision and hosted API URL, when the macOS installer is built, then it installs and launches on the declared macOS test version and uses the same reviewed API contract.

### Private link access

Given a participant is invited, when they use the private link, then only intended recipients can access the artifacts and the owner can expire or revoke that link.

### Artifact provenance

Given a build is shared, when the participant or owner inspects its release record, then it identifies the source revision, build date, app version, platform, artifact hash, API environment, and known install/signing limitations.

## Technical approach

Build release artifacts separately for Android and macOS Desktop, configure the production endpoint without embedding secrets, and verify HTTPS. Select a private file-delivery service only after provider terms/privacy review; do not assume a public GitHub release is private. Record whether code signing/notarization is available and its cost/requirements; do not claim it unless verified. Keep pilot artifacts revocable and do not store participant identifiers in the repository.

## Expected file changes

- Android release build/signing configuration and Desktop native distribution tasks.
- Release build/documentation scripts and `README.md` pilot installation instructions.
- `docs/risks-and-open-questions.md` with signing, link, and supported-version limits.

## Visual design impact

No product UI change. Follow `DESIGN.md` for any installation/help copy embedded in the app.

## Durable documentation impact

- `ARCHITECTURE.md`: not needed unless release configuration changes runtime boundaries.
- `CONSTRAINTS.md`: update only if a lasting signing/secret-handling invariant is introduced.
- `AGENTS.md`: not needed.
- `README.md`: document the private pilot install path and exact platform limits.

## Focused verification

<!-- verify:start -->
```sh
./gradlew :androidApp:assembleRelease :desktopApp:packageDmg
```
<!-- verify:end -->

## Appendix

See [`private_pilot_distribution.appendix.md`](private_pilot_distribution.appendix.md).
