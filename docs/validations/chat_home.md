# Validation — chat_home

> **Reconstructed archive.** No standalone validation record was saved when `chat_home`
> was accepted; the acceptance decision lives in commit `a79946f` ("chore: accept
> chat_home after validation"). This file was reconstructed on 2026-10-13 from that
> acceptance commit, `feature_list.json`, and `PROGRESS.md`, during a documentation
> consistency pass. It records the decision and the checks that were actually recorded.
> It is **not** a new independent review.

## Verdict

**Accept** — 2026-10-11. Feature id: `chat_home`. Spec: `docs/specs/chat_home.md`.
Validated revision: commit `47e80c8` ("fix: restore chat_home verification wrapper").

## Recorded checks

- `./init.sh` completes with the restored Gradle 9.8.0 wrapper and reports the current
  feature state; wrapper reproducibility was confirmed.
- `./gradlew :shared:jvmTest` passes.
- `./gradlew :desktopApp:build` passes and compiles the shared Compose starting screen.
- Scope, accessible labels, and the `commonMain`-only UI were reviewed against the spec.

## Environment limitation at acceptance

- `./init.sh --verify`, `./gradlew :shared:testAndroidHostTest`, and `./init.sh --android`
  stopped before compilation because the worktree had no `ANDROID_HOME` or
  `local.properties` with `sdk.dir`. No Android result was claimed.
- Desktop launch/manual smoke was not run because it is an interactive long-running
  target; compilation is covered by `:desktopApp:build`.

## Outstanding follow-up

- The spec's manual smoke ("open Android/Desktop, locate the Spanish field without adding
  a land, type a question, and confirm the action becomes available") was not executed at
  acceptance. It is not evidence of failure, and it can now be run in a checkout where the
  Android SDK is configured.

## Scope review

Only the `chat_home` implementation, its spec, Compose resources, tests, and the required
workflow/status documentation were changed. No backend, networking, land storage, or
later-feature behavior was added.
