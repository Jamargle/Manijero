# Validation — `environment_profiles`

## Verdict

**Accept** — 2026-11-02. Independent validation of the uncommitted diff against `docs/specs/environment_profiles.md`. Owner decision 6: the validator's accept is final; no owner walkthrough. Recommended state update: set `status` to `accepted`.

Feature id: `environment_profiles`. Claimed status: `passing`.

## Checks rerun

- `./scripts/init.sh --feature environment_profiles` — 187 passed, 2 skipped (published block accurate and runs; `bash -n` and both `git check-ignore` guards pass).
- `./scripts/init.sh --fast` — all 9 offline checks passed (backend 1777 passed, 4 skipped).
- `--verify` not rerun: the diff touches no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging files.
- Code and test review of `backend/app/environment_profiles.py`, the `local_rag_bootstrap.py` changes, the QA template, `.gitignore`, and the docs touched.
- Manual owner-guide steps against temporary homes were not run by hand: the sandbox refused env-prefixed `init.sh` runs. The subprocess tests in `test_environment_profiles_commands.py` drive `init.sh` with temporary homes and cover status before setup, QA setup, re-run, recovery, no-terminal, extra-argument exit 2, and old-style local settings.

## Focus points

- Never overwrite an existing token: `ensure_local_credentials` keeps any token of at least 32 characters and rebuilds only the clients file from its digest. It replaces a token only when it is empty or shorter than 32 characters. Such a token cannot be a valid client token (`pilot_config` requires 32 or more), so no working key is lost. This is a small, justified deviation from the spec's literal wording. QA replacement happens only after a typed `yes`.
- QA refusal: a missing or wrong `MANIJERO_ENVIRONMENT` or `MANIJERO_DEPLOYMENT_PROFILE` is refused with "this file is for QA, so it must say ...=pilot; it is never treated as local". Repeated or unknown keys and overlap with the local release root are tested.
- Secrets: the token is written with `O_EXCL` and mode 0600, and only digests go in the clients file. Nothing prints the token. `.gitignore` guards `*.token` and `pilot-clients*.json`. No token, clients file, or `.env` is among the untracked files. The template holds only `.invalid` hosts.
- Prod: `read_profile_settings("prod")` raises `prod_not_configured` and the status line is constant. The module has no network imports.
- Existing local files: the append path keeps every existing byte, and `read_settings` accepts the two new keys only with the local values.

## Findings

No blocking findings. Security: no relevant issues.

## Documentation and harness

The spec's durable-docs list is covered (`operations.md` MUST, `ARCHITECTURE.md`, owner guide, `backend/README.md`, risks row). `PROGRESS.md` and `known-limitations.md` lines are left to the orchestrator at acceptance.

## Remaining limits

- A local token shorter than 32 characters is replaced; this is documented only in code, not in the owner guide.
- The `--local-rag-setup` append path is covered by fakes only, per the spec.
- QA credentials exist only on this computer until `qa_server_deployment`.
