# `private_pilot_distribution` Appendix

## Repository research

- Android currently has a release build type but no release signing setup in the inspected Gradle file.
- Desktop declares Dmg/Msi/Deb package formats; accepted Desktop smoke evidence is macOS host-only and does not build an installer.
- Current clients use local development URLs; release wiring must select the reviewed HTTPS API endpoint.
- A repository README describes development builds and local service setup, not private pilot delivery.

## Implementation plan and tasks

1. Confirm the minimum Android and macOS versions/devices supported by the invite list; retain macOS-only Desktop scope.
2. Decide release signing/notarization and private artifact-link provider after cost and terms review; keep unresolved items as blockers.
3. Build release APK and macOS DMG from a clean revision with HTTPS endpoint configuration.
4. Install/launch both artifacts, verify API reachability, record hashes/provenance, and exercise link expiry/revocation.
5. Add concise private installation and recovery instructions; do not advertise public availability.

## Verification plan

- Run the focused Gradle packaging block, install on Android and macOS, and verify effective API URL and HTTPS.
- Test link access with intended and unintended accounts, expiry/revocation, and artifact hash.
- No persistent E2E harness exists; this is an artifact/host smoke.

## Evidence to capture

- Build revision, platform versions, package task output, APK/DMG hashes, endpoint environment, install smoke, private-link access/expiry, signing status.

## Feature evidence

## Validator checklist

- [ ] Only Android and macOS are represented as pilot targets.
- [ ] The build contains no secrets and reaches only the approved HTTPS endpoint.
- [ ] Private links are not public and can be revoked/expired.
- [ ] Signing/notarization claims match actual evidence.
- [ ] Artifact provenance and install limits are recorded.
