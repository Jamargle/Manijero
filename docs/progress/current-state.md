# Current state — narrative detail

This short narrative is on demand. [`PROGRESS.md`](../../PROGRESS.md) owns the current status,
limitations, and open checks; [`ARCHITECTURE.md`](../../ARCHITECTURE.md) owns technical boundaries;
[`CONTEXT.md`](../../CONTEXT.md) and [`CONSTRAINTS.md`](../../CONSTRAINTS.md) own current product
terms and durable rules.

## Product snapshot

- Manijero targets Android and Desktop. Shared business behavior and Compose UI live in
  `shared/src/commonMain`; iOS reuse is a future direction, not an MVP release commitment.
- The app provides Spanish chat, local land management, help, and privacy surfaces. Land data stays
  on the device in one `land-store-v2` aggregate (active and removed sections), migrated once from
  `land-store-v1`; removed lands stay local until permanently deleted. Search and summary are derived
  display state. Only the minimum land context allowed by the request contract may be sent with a
  question.
- The local FastAPI service exposes liveness-only `/health` and `/ask`. It uses no hosted model. The
  reviewed knowledge supports three procedural topics in the 2026 Andalusian PAC single application;
  the exact boundary and exclusions are in [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md).

## Evidence boundaries

The offline evaluators use synthetic fixtures, and the reviewed end-to-end answer evaluation is a
14-case sample over three approved topics and five boundaries. Its metrics are report-only, review is
author-only, and four case-level gaps remain visible (three earlier citation/critical-fact misses and
one out-of-scope reclamación answer). The Android and Desktop screenshot suite is a local
host-rendered pixel gate; it does not establish real-device rendering, accessibility, usability, or
iOS behavior. See [`PROGRESS.md`](../../PROGRESS.md), [`knowledge/pac_coverage.md`](../../knowledge/pac_coverage.md),
and the feature acceptance records for current gaps and exact evidence.

## Record locations

Feature behavior and verification are in `docs/specs/<feature-id>.md`; implementation planning and
raw evidence are in the sibling `.appendix.md`; acceptance evidence is in
`docs/validations/<feature-id>.md`. `feature_list.json` and `scripts/select-feature.sh` own current
feature status. [`docs/progress/session-log.md`](session-log.md) is a pointer index, not a second
evidence store.
