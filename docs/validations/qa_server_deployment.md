# Validation: qa_server_deployment

## Verdict

**Accepted** (2026-11-07) after the owner walkthrough; evidence-only acceptance, no second validator (see "Owner walkthrough" below).

**Accept, condition: pending owner walkthrough** (2026-11-03). Independent validation of the uncommitted diff against `docs/specs/qa_server_deployment.md`. Feature stays `passing` until the owner reports the "Owner walkthrough: QA" in `docs/owner-guide/qa.md` matched.

## Checks rerun

- `./scripts/init.sh --feature qa_server_deployment`: 404 passed (focused block is accurate and runs).
- `CI=true ./scripts/init.sh --fast`: all offline checks passed (backend 1943 passed, 4 skipped; harness 20 passed; gradle-jvm-test ok).
- `--verify` not rerun: the diff touches no `shared/`, `androidApp/`, `desktopApp/`, Gradle, or packaging files.

## Focus review

- Privacy gate: `qa_test_data_mode` requires exact `pilot` + `qa` + `yes` (no trimming or case folding). `pilot_gate` passes only a record whose `pilot_review.status` is exactly `pending` with the exact key set. Rejected, invalid, or unreadable records and other environments stay blocked. `evaluate_pilot_review` and the Gemini gate are untouched. Both consumers (`run_preflight`, `resolve_local_provider`) use it, and the launcher prints the spec warning and `privacy_review: pending (QA test data only)`.
- Loopback publish: `run_argv` publishes `127.0.0.1:<port>` only, runs with `--cap-drop ALL` and `no-new-privileges`, a fixed environment, a read-only clients-file mount, and `--restart no`. The entrypoint sets the public-bind acknowledgement for its own process only.
- Funnel: only the 443 entry pointing at `http://127.0.0.1:8100` counts as "ours". A foreign entry is refused as a prerequisite, and `funnel off` runs only for our own state. Stop turns Funnel off first and leaves the container running if that fails. Failed deploys turn off only the Funnel they started.
- Output: no token, question, or answer is echoed. The environment carries no token, only the digest-only clients file.

## Deviations judged

1. `test_local_rag_service.py` adds `qa_deployment` to the never-imported operator modules: acceptable and required by the existing rule.
2. `write_public_url` and `qa_test_data_only` are tested in the new files: acceptable, since the behavior is covered. The spec listed other test files only as "changed behavior only".
3. Narrowing the Dockerfile "no pilot word" check to `pilot_clients`/`pilot_privacy`: acceptable, because the launcher now legitimately ships. The check still keeps the pilot data files out.
4. Additive `local_container.py` changes (`image_id`, `container_info(name)`, `container_lock(busy)`, copied `serve_pilot.py`): backward compatible, and the existing `--container-*` tests pass.

## Limits remaining (only the owner walkthrough shows these)

- Real Tailscale account, HTTPS, and Funnel behavior, and the Funnel JSON shape parsed from a real `tailscale` CLI.
- Docker Desktop can read the clients file through the bind mount.
- The container reaches Ollama through the relay on the Mac.
- A phone browser opens `<address>/health`; update and rollback swap images for real.
- At acceptance, record in `docs/risks-and-open-questions.md`, `docs/progress/known-limitations.md`, and `PROGRESS.md`: QA needs the Mac awake, Funnel exposes a public hostname, test-data-only is a rule and not a technical filter.

## Owner walkthrough (2026-11-07)

Owner ran "Owner walkthrough: QA" on their Mac and reported every step matched, except step 6.

- Steps 1-5, 7, 8: matched. Tailscale HTTPS certificates and Funnel had to be enabled in the Tailscale admin pages first (the first `--qa-deploy` correctly refused and named the step). Deploy printed `Result: QA is running at https://<mac>.<tailnet>.ts.net for test data only.`, a phone on mobile data opened `/health`, and the QA app answered a made-up question.
- Step 6 (update and roll back): **not exercised**. With no newer image there was nothing to update, so there was nothing to roll back to. Real image swaps are still unverified live, and only the tests cover them.
- The guide's `tailscale status` check fails when the Tailscale CLI is not on `PATH`; the deploy tool already falls back to the app's bundled CLI.
