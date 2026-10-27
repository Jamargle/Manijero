# `official_source_discovery` acceptance

## Verdict

**Accepted** on 2026-10-27.

## Independent verification

- `MANIJERO_PYTHON=backend/.venv/bin/python ./scripts/init.sh --feature official_source_discovery` — passed, 636 tests.
- `./scripts/init.sh --fast` — passed, all nine checks.
- Confirmed mixed valid/malformed BOE and BOJA registry responses report unchecked, preserve prior candidates and `last_success_at`, and do not partially commit candidates.
- Reviewed the BOE and BOJA adapters, bounded request behavior, exact host and redirect checks, separate candidate state, and pending human-review gate.
- Confirmed the canonical source catalog and passage artifacts are not written by discovery.

## Accepted scope and limitations

BOE daily sumario XML and BOJA calendar/bulletin JSON discovery are implemented with provenance, deduplication, changed observations, transactional failure handling, and a manual CLI. FEGA and MAPA remain explicit unchecked coverage gaps; discovery does not imply complete registry coverage or legal validity. The live endpoints were smoke-tested, but the local Python certificate store rejected BOE TLS during a CLI-level live attempt, so live candidate-state creation was not verified. No TLS verification was disabled.

See [`official_source_discovery.appendix.md`](../specs/official_source_discovery.appendix.md) for detailed evidence and exact smoke limitations.
