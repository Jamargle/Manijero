# Constraints: Answers, retrieval, and knowledge

Durable MUST/MUST NOT rules for backend answer path, retrieval, generation, evaluation, campaign scope, and knowledge updates. Part of the index in [`CONSTRAINTS.md`](../../CONSTRAINTS.md); paths in backticks are relative to the repository root.

## Answer grounding

- **MUST**: no component may emit a user-visible answer claim that has not passed
  `backend/app/generation.py::verify_draft`. A draft produced by a hosted model,
  a prompt, a cache, or any future generator must be discarded **whole** when it
  fails, never partially emitted, repaired, or replaced by model or unreviewed
  knowledge. Reason: `grounded_answer_generation` established that code — not a
  model — is the authority on whether an answer may be shown, and an
  unverified claim is exactly the failure a wrong Spanish deadline or amount
  would come from.
- **MUST**: a user-visible answer's citation markers, its `sources` array, and
  the orientative notice are owned by code (`generate_grounded_answer` /
  `to_answer_response`), never by a generator. Draft markers are verified as
  original retrieval candidate ranks; emitted markers MUST be dense response-
  local positions, so `[n]` selects `sources[n-1]`. Reason: sparse retrieval
  ranks cannot be exposed as response indexes, and the notice is a fixed
  orientative line, not generated prose.

## Local embeddings

- **MUST**: the default answer behavior MUST stay the accepted BM25 retrieval
  with every code-owned answer property unchanged. An embedding model may run on
  the `/ask` path only through the explicit hybrid opt-in
  (`MANIJERO_RETRIEVAL_MODE=hybrid`, `chroma_hybrid_retrieval`); any other
  composition is a separately reviewed change. A missing optional runtime, a
  missing/invalid artifact, or a stale derived index or store MUST NOT alter an
  answer, citation, abstention, or land clarification. Reason:
  `local_bge_m3_embeddings` added an optional capability, not a new answer
  authority; silently swapping retrieval on a host without the model would
  weaken grounding without review.
- **MUST**: an embedding model may load only from a local artifact directory
  whose immutable upstream revision and every per-file SHA-256 match the pinned
  configuration, with hub/network access forced off. A model name, branch, or
  tag MUST NOT be loaded directly. A changed pin is a new reviewed configuration,
  never an edited checksum. Reason: an unpinned model silently changes vectors,
  storage, and results, and no download belongs on the answer-service host.
- **MUST**: a derived embedding index MUST be written outside `knowledge/`, MUST
  NOT contain passage text, and MUST NOT be treated as reviewed canonical
  knowledge. It MUST record the model pin and its catalog/passages/`as_of`/
  campaign inputs, and MUST be reported stale instead of reused when any of them
  change. Reason: the index is reproducible derived data; promoting it into the
  reviewed corpus would create a second, unreviewed answer source.

## Hybrid retrieval

- **MUST**: a vector or fused ranking MUST compose into `app.retrieval.Retriever`
  only through `Retriever.with_ranker`; it MUST NOT construct `RetrievedPassage`
  values, re-implement eligibility, or bypass the lexical gate. A question with no
  positive BM25 match MUST return no candidate in every mode, and only passages
  the retriever admitted may be returned. Reason: `chroma_hybrid_retrieval` kept
  approved-source provenance and zero-evidence abstention code-owned; vector
  similarity is positive for almost any text, so without the gate it would turn
  unrelated questions into answers.
- **MUST**: hybrid ranking MUST be used for a request only while the store
  manifest matches the current model pin, active campaign, and the digest of the
  exact admitted `(passage_id, text)` documents; otherwise, and on any load or
  query failure, the request MUST use the unchanged BM25 ranking and log only a
  fixed reason code or exception type name. Importing the service MUST NOT import
  `chromadb`, `torch`, or the vector/hybrid modules. Reason: a stale or broken
  vector store must degrade to the reviewed behavior, never to an answer from
  passages that are no longer admitted, and third-party error text can echo a
  question.
- **MUST NOT**: change the default retrieval mode to hybrid, or claim a retrieval
  or answer improvement, without a measured BM25 vs hybrid comparison on reviewed
  cases recorded with the change. Reason: the 2026-10-31 comparison on the
  14-case author-only sample measured no answer-level difference.

## Abstention

- **MUST**: no component may emit an abstention that carries a source, a figure,
  or a date, and abstention copy is code-owned (`ABSTENTION_MESSAGES` /
  `to_abstention_response`), never generated, paraphrased, or supplied by a
  caller. An abstention payload is exactly the accepted `AskResponse` keys with
  `status: "abstained"`, `sources: []`, `land_ids_to_choose: []`, and one pinned
  plain-Spanish message with no digit and no date. Reason: the point of
  abstaining is to avoid an invented deadline or amount; leaking evidence or
  figures into the "I cannot answer" path would reintroduce exactly that failure,
  and generated abstention prose could contradict the pinned counsel to consult
  the Oficina Comarcal Agraria or the cooperative.

## Safety evaluation

- **MUST**: a land-safety evaluation case MUST be source-anchored and human-reviewed: it names the
  sources it expects, and a case whose expectation turns on a critical fact (a deadline, an amount,
  a threshold) MUST NOT enter the set without a completed `review` block (reviewer, review date,
  level, `<source_id>#<location>` anchor) — a critical case without it fails closed at load time.
  The harness MUST run the accepted end-to-end decision (`answer_with_clarification`) unchanged and
  MUST NOT re-implement eligibility, grounding, or clarification, MUST report coverage metrics
  report-only (a safety invariant leak may fail, a coverage mismatch only with `--fail-on-miss`),
  and MUST NOT treat any metric as a release gate until a measured baseline is reviewed and
  enforcement is agreed separately. Reason: `land_safety_evaluation` established the reproducible
  synthetic baseline; a gate whose numbers came from synthetic fixtures, or a case whose critical
  fact nobody checked, would turn an unverified expectation into a false safety guarantee.

## Campaign scope

- **MUST**: `/ask` requires an explicitly configured four-digit active campaign, independent of
  the UTC source-validity date. Never infer the campaign from the date, question, land, or evidence;
  only neutral and exact-active-campaign sources may reach generation, and malformed scope fails
  closed. Expired campaign records must be rotated out of active artifacts with their passages.
  Reason: `backend_campaign_validity` prevents evidence for one PAC campaign being mistaken for another.

## Coverage disclosure

- **MUST**: the pinned coverage disclosure MUST name only topic areas represented by the reviewed
  corpus, MUST state the enforced limits (cooperative-specific practices, personalized amounts or
  eligibility, out-of-corpus topics), MUST NOT contain a deadline, amount, threshold, article number,
  eligibility claim, or invented contact detail, and MUST be updated in the same change that widens
  or narrows corpus scope. Reason: `coverage_and_help` establishes that people must not infer broad
  coverage from the assistant; stale or overconfident disclosure could prompt reliance outside the
  evidence actually reviewed.

- **MUST**: restyling the help and privacy surfaces MUST preserve their pinned copy, disclosure facts,
  shared-attribute mapping and existing navigation callbacks; visual grouping MUST NOT introduce a
  new promise, warning/status implication, route or external link. Reason: `help_privacy_refresh` is
  visual adaptation only; changing the facts or their implied certainty during a restyle could make
  the screens contradict the reviewed corpus or the actual local/request data boundary.

## Knowledge updates and retrieval

- **MUST**: source scans and document ingestion MUST write only quarantined candidates; they MUST NOT
  make a new or changed document answerable without human approval. Candidate records MUST preserve
  official URL, retrieval time, original-content hash, parser/version provenance, and review status.
  Reason: a new publication can be inapplicable, superseded, malformed, or adversarially formatted.
- **MUST**: scheduled source checks are best-effort and MUST expose last-success time, failures, and
  missed runs; a schedule alone MUST NOT be represented as proof that the corpus is current.
  Reason: external schedulers and official sites can delay or fail.
- **MUST NOT**: add a repository-hosted schedule (for example a `.github/workflows` `schedule:` trigger)
  that scans official sources or invokes `run_source_updates.py`; scheduled source checks run only from
  operator-installed host units. The scheduler MUST write only operational state (monitor/discovery
  state, ledger, lock) in a state directory outside the repository and outside `knowledge/`, and its
  tests MUST stay offline (sockets blocked, fakes only). Reason: `knowledge_update_scheduler` — a
  merged repository schedule would make real requests to official sites without an operator choice,
  and committed state would bypass human-reviewed canonical changes.
- **MUST**: change-impact analysis MUST stay read-only over approved knowledge and MUST NOT retire,
  replace, re-approve, or re-date a source, passage, evaluation case, index, or answer. Every
  potentially affected candidate MUST remain review-required, and an ambiguous publication,
  amendment, repeal, or validity signal MUST NOT authorize retirement or be dropped silently: every
  ambiguous signal, negated wording included, MUST make its candidate review-required even when it
  links no approved source or links only a reviewed passage or evaluation case. Reason:
  `legal_change_impact_analysis` detects wording; only an identified human can decide what a legal
  change means for the reviewed corpus.
- **MUST**: canonical catalog and passage changes MUST go through the controlled merge that verifies
  an explicit approval by a named requested reviewer other than the proposal author, a matching
  package/checks/case digest, all required checks passing, and current canonical bytes matching the
  reviewed baseline. A proposal that changes the reviewed corpus MUST supply the reviewed
  answer-evaluation case set; preparation MUST validate the **after-state** and block readiness with
  the orphaned case ids, and merge MUST require the same digest-bound case set and revalidate it.
  Without cases, a catalog/passage change MUST be blocked (a no-op proposal may pass). A bot, CI
  status, label, or matching hash MUST NOT count as approval; the commands refuse known automation
  identities but identities are not authenticated; a rejected or changes-requested package MUST
  leave canonical knowledge byte-identical; and merge MUST NOT reindex, release, or deploy. Canonical
  after hashes and writes MUST preserve the field order of entries the proposal does not rewrite, so a
  no-op merge is byte-identical; a newly added or rewritten entry may take the proposal's own
  serialization.
  Reason: `knowledge_update_review_pr` keeps approval with a person and separates a bounded reviewed
  merge from publication; an unreviewed case set or a reordered file would hide corpus drift.
- **MUST**: a knowledge release MUST be built only from canonical artifacts bound to human-approval
  evidence (a `merge.json` whose hashes equal the candidate bytes, or an explicitly recorded reviewed
  Git baseline), MUST rebuild indexes from them and record artifact, runtime, and model versions, and
  MUST pass structural, grounding, and per-case no-regression gates that force BM25 retrieval and
  extractive generation regardless of environment. A release whose gate failed MUST NOT be published,
  rolled back to, or served. Publication MUST be a single atomic pointer swap (`current`) under a lock
  that records the previous release, so rollback to the prior release is one step. The manifest MUST
  NOT carry a timestamp, reviewer name, or other personal value (timestamps live only in the release
  log), and a release root MUST NOT live under `knowledge/`. With `MANIJERO_KNOWLEDGE_RELEASE_ROOT`
  set, each request MUST read both corpus files from one verified release; unset MUST keep today's
  checkout read path.
  Reason: generated indexes are derived data and must not drift from reviewed sources; `knowledge_reindex_release`
  replaced the non-atomic two-file corpus replace with immutable, hash-verified releases.
- **MUST**: retrieval changes MUST be compared with the measured BM25 baseline on the reviewed cases;
  report-only metrics MUST NOT be described as improved answer quality without sufficient reviewed
  evidence.
