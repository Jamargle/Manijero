# Validation: client_environment_builds

Verdict: accept (independent validator, 2026-11-02; final per owner decision 6, no walkthrough).
Spec: [../specs/client_environment_builds.md](../specs/client_environment_builds.md) · Appendix: [../specs/client_environment_builds.appendix.md](../specs/client_environment_builds.appendix.md)

## Checks rerun

- `./scripts/init.sh --feature client_environment_builds` (all 7 published lines, incl. bash -n, git check-ignore, jvmTest platform/connection/welcome, Android and Desktop compiles): passed.
- `check-environment-build.sh`: local default unchanged and ignores bad address file and QA key; QA gives `.qa` id, `Manijero QA` label, file address, key only in debug BuildConfig and Desktop run folder; switching QA to local reuses no QA output; placeholder notice; bad environment, address, and key fail plainly without content; ends back in local.
- `check-pilot-token-build.sh`: passed (release and jar hold no token).
- `./scripts/init.sh --fast`: all 10 offline checks passed.
- `--verify` not rerun: the focused block already compiled both apps and ran the build-output checks; no device surface is in scope.

## Review notes

- PilotTokenGuardTest loosening is narrow: the blanket `inputs.property` ban became an exact list (`environment`, `askBaseUrl`, count-checked); `resources.srcDir` is pinned to the environment resource only. No token rule weakened.
- Local builds read only `pilot-token.local` (or the override); QA only the QA key path (or the override). The address file is read only when QA.
- Only `.invalid` placeholder committed; `/qa-address.local` is git-ignored. Durable docs (ARCHITECTURE, constraints, owner guide, AGENTS, backend README, limitations) updated.
- Nit, not blocking: `--help` line in `usage` lost one alignment space.

## Limits that remain

- QA address is a placeholder until `qa_server_deployment`; no QA build has run on a device (`qa_real_device_check`).
