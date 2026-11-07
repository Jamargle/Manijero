# Acceptance record: question_scope_guard

Verdict: accept (validator, 2026-11-07). Spec: [question_scope_guard](../specs/question_scope_guard.md); evidence: [appendix](../specs/question_scope_guard.appendix.md).

## Checks rerun
- `./scripts/init.sh --feature question_scope_guard`: passed (546 tests; eval below).
- PAC eval (`--active-campaign 2026 --as-of 2026-11-07 --k 5`): states 14/14 (baseline 12/14), sources 8 (=8), critical facts 9 (=9), `unexpected_answers` 0; `tema-no-cubierto` and `reclamacion-fuera-de-alcance` abstain with no sources.
- `./scripts/init.sh --fast`: only the 2 `test_procedure_map.py` failures inherited from the main merge (procedure_map.json lists 4 PAC sources, catalog has 6). The diff does not touch `procedure_map.*`, the catalog, or passages.
- Spot check of in-scope phrasings: modification deadline, sede electrónica, SIGPAC recinto, filing deadline, synthetic importe ficticio are untouched.
- Privacy: the guard only builds `GroundingIssue("out_of_scope_question", <omission label>)`; no logging in the module. No new dependencies. Shared `--verify` not rerun (no `shared/` or Gradle changes).

## Limits that remain
- Lexical and conservative: unlisted paraphrases still reach retrieval.
- Deliberate over-block: "¿Tengo derecho a modificar mi solicitud?" abstains as individual eligibility (safe direction).
- The three known citation misses and the `plazo-modificacion-parcelas-2026` ranking issue (singular/plural trial) are unchanged.
