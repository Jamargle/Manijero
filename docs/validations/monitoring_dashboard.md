# Validation: monitoring_dashboard

Verdict: accept, condition "pending owner walkthrough" (independent validator, 2026-11-02). Status stays `passing` until the owner reports the walkthrough matched the guide.

Spec: [../specs/monitoring_dashboard.md](../specs/monitoring_dashboard.md) · Evidence: [appendix](../specs/monitoring_dashboard.appendix.md)

## Checks rerun

- Published focused block (monitoring + local_container tests): 132 passed, 2 skipped (Docker smoke and digest test, both by design). The block is accurate and runs.
- `./scripts/init.sh --fast`: all 10 offline checks passed (backend 1925 passed, 6 skipped; harness 20 passed).
- `--verify` not rerun: the diff touches only `backend/`, `scripts/init.sh`, docs, and the feature index; no `shared/`, apps, Gradle, or packaging.
- Not run: Docker-backed smoke, live Prometheus/Grafana rendering, live QA scrape (no Docker session here).

## Review

- Privacy: Prometheus `metric_relabel_configs` keep only `manijero_*` and `labelkeep` of the `backend_health_metrics` allowlist plus env/job/instance/exported_job; the dashboard and rules reference only aggregates. QA token is a read-only mounted file (`credentials_file`), never argv; Grafana admin password passes by `-e NAME`.
- Network: only Grafana is published, `127.0.0.1:<port>:3000`; Prometheus unpublished; containers drop all caps; label `org.manijero.managed=1` gates every stop/remove.
- Grafana: anonymous Viewer, login form, Explore, plugin admin, analytics, update checks, alerting off.
- Dashboard: Local and QA rows, four stat panels each, value mappings carry state word, meaning, and first action (with the exact command), plus neutral and "Not set up yet" text; "How to read this page" panel present. Thresholds match `thresholds.json` (checked by tests). QA without a real address shows "Not set up yet ... Nothing to do until the QA service is deployed" (via `absent(up{env="qa"})`, no QA scrape job generated).
- Operations rule: `docs/constraints/operations.md` amends the Monitoring MUST with "Owner decision (2026-11-02)" and cites the spec; the new MUST covers loopback, pins, series/label keep, Anonymous Viewer.
- Docs: ARCHITECTURE, owner guide, backend README, known limitations, and PROGRESS updated; `local_monitoring` added to the service-never-imports guard.

## Deviation accepted with a tracked follow-up

- Image pins are explicit version tags with `digest: null` (`grafana/grafana-oss:12.0.0`, `prom/prometheus:v3.4.0`); spec scenarios 1 and 6 ask for `tag@sha256`. Judged acceptable, not a revise: the offline implementer could not read registry digests and invented none, the loader/command already use `tag@digest` once present, the rule and README state the interim openly, `test_image_pins_carry_digests` skips only while null, and the images are official, version-fixed, and reach only loopback. A mutable tag is a weaker supply-chain guarantee than the spec promised.
- Follow-up (developer, needs network, not the owner): read the index digests, fill `backend/monitoring/images.json`, rerun the focused block so the digest test runs (not skip), then tighten the operations.md wording. Do this before the next monitoring change or `qa_service_alerts`.

## Remaining limits (only the walkthrough or later work shows these)

- The page actually renders and reads clearly in a browser, including at 200 % zoom.
- Local row goes grey/red with the service stopped and green after `--local-rag-start`.
- Grafana 12 accepts the provisioning files and env settings and the container starts healthy.
- Runs only on the owner's Mac; not alerting; QA scrape unverified live; thresholds are initial.
