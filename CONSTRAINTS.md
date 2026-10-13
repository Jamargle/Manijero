# Manijero Durable Constraints

Operational MUST/MUST NOT rules that future features have to respect on top of
`AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, and the accepted contracts.

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
  `to_answer_response`), never by a generator. Reason: marker `[n]` must keep
  meaning `sources[n-1]`, and the notice is a fixed orientative line, not
  generated prose.

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
