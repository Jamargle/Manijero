# Validation — suggested_questions

## Verdict

**Accept**

## Independent checks

- Reviewed `docs/specs/suggested_questions.md` against the diff: `ChatHomeAction.SuggestedQuestionSelected(String)`,
  the pure reducer case, the shared suggestion section in `ChatHomeScreen`, the Compose resources,
  the new reducer tests, and the previews are all present and match the spec's technical approach.
- Confirmed the three shipped strings byte-for-byte (`¿Qué necesito preparar para la solicitud única?`,
  `¿Qué es el SIGPAC y para qué sirve?`, `¿Qué obligaciones tengo por la condicionalidad?`) against the
  spec Content decision with a Python equality check; order matches (solicitud única, SIGPAC,
  condicionalidad); no extra example is shipped. The unapproved deadline wording
  (`¿Hasta cuándo puedo cambiar mi solicitud?`) appears only in `docs/archive/MasterPlanV3.md`, the spec prohibition,
  and the PROGRESS non-shipped note — never in a shipped resource or UI literal.
- Reducer (`ChatHomeState.reduce`) sets `question` to the supplied text and clears `submittedQuestion`,
  performs no I/O, and adds no dependency/ViewModel/route/platform adapter. `canAsk` (non-blank) enables
  `Preguntar` after a selection.
- Ran `./gradlew :shared:jvmTest --rerun-tasks`: BUILD SUCCESSFUL, `ChatHomeStateTest` 7/7 (0 failures),
  including replacement, stale-state clearing, verbatim submit plus later edits, and the
  Spanish/Unicode case; the pre-existing whitespace-rejection and original-wording submit tests still pass.
- Ran `./scripts/init.sh --verify`: BUILD SUCCESSFUL. Forced `:shared:testAndroidHostTest`
  (`ChatHomeStateTest` 7/7), `:androidApp:assembleDebug` (`androidApp-debug.apk` present), and
  `:desktopApp:build` with `--rerun-tasks`, all passing with the SDK now resolved via
  `local.properties` (`sdk.dir=/Users/jose/Library/Android/sdk`).

## Scope review

Changed files are limited to the spec, `App.kt`, `ChatHomeState.kt`, `ChatHomeStateTest.kt`,
`strings.xml`, `PROGRESS.md`, and `feature_list.json`. No changes to `androidApp`/`desktopApp`
entry points, Gradle dependencies, `scripts/init.sh`, backend/contracts, land storage, or navigation.

## Accessibility notes

Examples are `OutlinedButton` controls whose `Text` label is the full question, laid out in a
vertically scrolling `Column` within the existing 720dp content width with `TextAlign.Start`; they
wrap rather than ellipsize and rely on the outline shape plus label (not color alone). Material
`OutlinedButton` provides built-in keyboard focus/activation and screen-reader semantics. No Compose
UI-test framework exists, so keyboard/emulator behavior was reasoned from Material semantics and the
implementer's recorded emulator smoke; it was not re-executed in this non-interactive validation.

## Environment limitations

`:desktopApp:run` is interactive/long-running and was not launched here; Desktop evidence rests on
`:desktopApp:build` plus the implementer's recorded launch smoke. Android emulator UI smoke
(large-text wrapping, tap-to-fill) was not independently reproduced; the recorded claim is consistent
with the read code and the passing non-interactive checks above.
