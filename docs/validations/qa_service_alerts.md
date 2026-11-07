# Validation: qa_service_alerts

- Verdict: accept, condition `pending owner walkthrough` (validator, 2026-11-07). Spec: [qa_service_alerts.md](../specs/qa_service_alerts.md); evidence: [appendix](../specs/qa_service_alerts.appendix.md).
- Scope: operator-only (backend, `scripts/init.sh`, docs). No `shared/`, apps, Gradle, contracts, or knowledge changes, so `--verify` was not rerun.

## Checks rerun (independent)

- `./scripts/init.sh --feature qa_service_alerts`: 195 passed (bash -n plus the four published test files).
- `CI=true ./scripts/init.sh --fast`: all 10 offline checks passed (backend 2596 passed, 7 skipped).

## Review

- State machine (`advance`): 2-in-a-row confirm, one alert, 4-hour reminder, 60-minute same-kind cap, recovery after 2 OK checks only when an alert was sent, failed send retried next check. Matches scenario 5.
- Secrets: token used in-process; Telegram and metrics failures collapse to fixed codes (broad `except` so no URL leaks); plist holds only python, script, `check`, and PATH; logs and state hold times, kind codes, outcomes.
- launchctl: `SystemLaunchctl` builds every call from the single label `org.manijero.qa-alerts` and `gui/<uid>`.
- Tests: fake Telegram on a loopback socket, fake launchctl/Docker/Tailscale, temporary homes, fake tokens only.
- Docs: operations.md (amended MUST plus new MUST), owner-guide (three sections), known-limitations, ARCHITECTURE, backend/README all updated as the spec lists. No unrequested files changed.

## Notes (non-blocking)

- Cosmetic: the `--android` usage line in `scripts/init.sh` lost two spaces of indentation.

## Only the owner walkthrough can show

- A real BotFather bot token is accepted and the chat id is found.
- The test alert arrives on the phone.
- launchd runs the job every 5 minutes (and the macOS "Background item added" notice is as described).
- A real stop of QA produces the alert, then the "back to normal" message.
