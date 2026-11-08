# Validation: usability_session

Spec: [usability_session.md](../specs/usability_session.md) · Appendix: [usability_session.appendix.md](../specs/usability_session.appendix.md)

## Verdict

**Accept, condition: pending owner walkthrough.** The kit and recorder satisfy the spec. The feature stays `passing` until the owner runs a real session with 2-3 low-confidence participants and reports that it matched the guide; only then `accepted`.

## Checks rerun

- `./scripts/init.sh --feature usability_session`: passed, 66 tests, offline.
- `CI=true ./scripts/init.sh --fast`: passed, all 10 checks (backend 2582 passed, 7 skipped; harness 20 passed).
- `--verify` not rerun: the diff touches no `shared/`, app, Gradle, or packaging files.
- Kit: five Spanish files in `docs/usability-session/`; consent note covers app-not-person, stop any time, no faces or voices, no names, made-up data, spoken agreement without signature. Observation sheet has a P-code box, three outcomes per task, minutes, notes with the no-names reminder, no name, contact, or age field.
- Tests pin every quoted app label against `strings.xml`, the task order, and the honest task 3 case (land choice yes/no).
- Recorder tests cover refused codes and notes without echo or storage, three refusals (exit 1), end of input, Ctrl+C, declined recap (file identical), replace asks `yes`, unreadable file, extra argument (exit 2, no prompt), home inside checkout refused, and an `init.sh` subprocess.
- All recorder runs use a temporary `MANIJERO_USABILITY_HOME`; no test uses the real `~/manijero`.
- `.gitignore` guards `usability-results*.json`; the default results file is outside the checkout.
- Owner guide section `Owner walkthrough: usability session`: 6 numbered steps, missing-prerequisite case, recovery, message table (about 35 lines).
- `scripts/init.sh`: dispatch with misuse check and "not set up yet" pair, `usage`, and `--check` listing updated.

## Not run by me

- A live interactive run of the command (sandbox blocked the temporary-folder variable form); the piped-input and subprocess tests cover the same paths.

## What only the walkthrough can show

- Whether the printed kit and script work for a facilitator without the developer present.
- Whether participants understand the task cards and consent wording.
- Whether the Desktop QA reset steps between participants work as written.
- Whether the app ever asks to choose a land (corpus has no `applicability`, so likely not).
- Whether the prompt flow of `--usability-record` is clear to the owner.

## Remaining limits

- Note screening is lexical: it can miss unusual personal data or refuse harmless words (documented in `backend/README.md` and `docs/progress/known-limitations.md`).
- No user findings exist yet; they become follow-up items later.
- Security: no personal data is echoed, logged, or stored; file mode 0600, folder 0700; no issues found.

## Owner walkthrough (2026-11-08)

- Owner reported the usability session completed successfully on the Desktop QA app with made-up data, results recorded with --usability-record under anonymous codes. Number of participants, per-task outcomes and findings were not reported here; they stay in the owner's local results file (~/manijero/usability/usability-results.json), which agents do not read.
- Status set to `accepted` on that report; no second validator (evidence-only update).
