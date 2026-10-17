# Appendix — `chat_home`

Planning and verification record for [`docs/specs/chat_home.md`](chat_home.md), moved out of the
contract on 2026-10-17 without rewording. Sections: repository research, implementation plan and
tasks, verification plan, evidence to capture, implementation findings, validator
checklist, and feature evidence. `docs/validations/chat_home.md` remains the authoritative
acceptance record.

## Feature evidence

Moved verbatim from `feature_list.json` on 2026-10-17, when that file became a lean index
(status, dependencies, and verification only). `feature_list.json` remains authoritative
for status and dependencies, and `docs/validations/<feature-id>.md` remains authoritative
for the independent acceptance record.

- Spec: docs/specs/chat_home.md.
- Reproducible project wrapper restored from the project setup (Gradle 9.8.0); ./scripts/init.sh completes successfully.
- ./gradlew :shared:jvmTest passes; ./gradlew :desktopApp:build passes and compiles the shared Compose screen.
- ./scripts/init.sh --verify, ./gradlew :shared:testAndroidHostTest, and ./scripts/init.sh --android are blocked before compilation because this worktree has no ANDROID_HOME or local.properties sdk.dir.
- Self-verification passes for the implemented shared/Desktop scope; Android verification remains environment-blocked and is not claimed.
- Independent validator accepted commit 47e80c8 after confirming scope, accessibility labels, wrapper reproducibility, and all feasible checks. Record: docs/validations/chat_home.md.
