# `pac_evidence_expansion` Appendix

## Repository research

- `PROGRESS.md` limits the corpus to three procedural topics and states that the current six-case evaluation has known citation and critical-fact misses.
- `backend_answer_evaluation` owns the deterministic report-only evaluator and canonical cases.
- `backend_citation_hardening` owns response-local citation numbering; `backend_pac_corpus` owns approved source passages and coverage.

## Implementation plan and tasks

1. Capture the baseline case-level report and enumerate every known mismatch before edits.
2. Build a topic/boundary coverage matrix from `knowledge/pac_coverage.md`; author cases only for approved passages and expected abstention/clarification boundaries.
3. Review each case and critical fact against the cited official passage as project author; label review role honestly.
4. Fix source, code, or evaluator errors at their owning boundary; preserve unresolved cases in the final report.
5. Run twice with pinned date/campaign/retrieval settings and update coverage/evidence notes with exact counts and limitations.

## Verification plan

- Run evaluator tests and canonical evaluator twice with the same flags; compare complete output.
- Validate every case source/passage against the canonical catalog and passages.
- Confirm no new legal topic, unsupported fact, user-derived data, metric threshold, or independent-review claim appears.

## Evidence to capture

- Baseline and final case-level outputs, current case/topic counts, each prior miss and resolution, fixed inputs, exact author-review method, residual gaps.

## Feature evidence

## Validator checklist

- [ ] Known misses remain traceable and are fixed or reported unresolved.
- [ ] Cases stay within the current reviewed corpus and declared campaign.
- [ ] Review is labeled author-only; no independent legal assurance is implied.
- [ ] Outputs are deterministic and quality metrics remain report-only.
- [ ] The published description states exact case count, topics, and omissions.
- [ ] User research, defense/demo, and unsupported topics are not added.
