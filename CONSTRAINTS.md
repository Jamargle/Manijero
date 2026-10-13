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

## Client request failure

- **MUST**: a request that failed or never reached the answer service MUST NOT be rendered as an
  answer, and recovery MUST keep the exact original wording. The failure lives in
  `ChatHomeState.failure` and is shown as a separate notice — never a transcript entry, never an
  `Asistente` label — while `RetryClicked` re-sends `ChatHomeState.failedQuestion` verbatim and
  appends no second user message (`ChatConversation` classifies the thrown failure; the transport
  signals are the payload-free `AnswerServiceUnavailableException`/`AnswerServiceErrorException`).
  Reason: `network_error_recovery` established that a person must never believe an unanswered
  question was answered, and `response_states`/`answer_source_cards` will render this transcript
  next, so a retryable failure must keep the question recoverable and out of the answer stream.

## Client response states

- **MUST**: a supported answer and an abstention MUST stay distinguishable in the transcript, and
  no answer MUST receive a confident legal-certainty treatment (no badge, checkmark, success green,
  or "verificado" wording). Every assistant entry MUST carry the `answerStatus` it arrived with
  (copied from the decoded `AskResponse.status`, never inferred from `lastResponseStatus`); an
  abstention MUST render its code-owned message verbatim in the transcript with the non-confident
  caution treatment plus an explicit text state label, and MUST NOT add a source, citation marker,
  figure, date, land name, or client-authored next step, nor branch on an abstention reason (the
  wire payload carries none). Reason: `response_states` established that a person must never read a
  "no lo sé" as a rule or mistake a real answer for legal certainty; `answer_source_cards` and
  `chat_accessibility` render this transcript next.

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

## Land editing

- **MUST**: editing a land MUST update exactly one stored record: it carries every attribute the
  edit form does not collect (`areaHectares`, `notes`) through unchanged, preserves the targeted
  `id` and `createdAtEpochMillis`, never calls `create`/`delete`, and MUST NOT report an update as
  saved when `update` returned `null` or threw. Reason: `edit_land` established that correcting one
  detail must never rewrite another land or silently erase stored data.

## Client source cards

- **MUST**: every assistant entry MUST render only the `sources` its own decoded response carried
  (copied at the single creation site `ChatHomeState.ResponseReceived`, never from
  `lastResponseStatus`); the client MUST NOT invent a source, excerpt, date, or link, MUST open only
  an https URL, MUST NOT render a source, reference, figure, or date on an abstention, and MUST NOT
  alter the answer's claim text — only a `[n]` token may become a reference numeral, and only when
  the reply's distinct markers line up exactly with `sources` (a non-conforming payload rewrites
  nothing). Reason: `answer_source_cards` established that marker `[n]` means `sources[n-1]` only
  for a conforming cited set, so a mismatched or non-https payload must fail closed rather than point
  at the wrong document; `chat_accessibility` and `answer_land_scope` render this transcript next.

## Land removal

- **MUST**: removing a land MUST delete exactly one stored record, by its local id, through
  `LandRepository.delete`; it MUST NOT rewrite, reorder, or otherwise change any other record, MUST
  NOT call `create`/`update` from a removal path, MUST remove nothing before an explicit confirmation
  that names the land being removed, and MUST NOT report a removal that `delete` did not confirm (a
  `false` result or a thrown failure is never a removal). Reason: `remove_land` established that a
  person's other lands and their local-only store must survive a removal untouched, and that a
  permanent local action must never be claimed when it did not happen.

## Client land context

- **MUST**: the `land_context` sent with a question MUST carry every stored land whenever at least
  one exists — `mode: all_active`, repository order, opaque local ids verbatim — and, per land, only
  the optional attributes the question actually needs (`municipality`, `water_regime`,
  `production_method`); it MUST NOT carry a land name, free-text note, area, timestamp, or any
  contract-unknown key, MUST send a needed but unknown stored value as `unknown` (never a guess),
  MUST omit a value it does not have (an unset `municipality`) rather than a placeholder or an empty
  string, MUST use `mode: general` with `lands: []` only when no land is stored, and MUST NOT rewrite
  the person's exact wording or change the attribute decision silently (a vocabulary change is a spec
  and test change). Reason: `minimal_land_context` established that the device's private labels and
  details never leave it with a question, that omission in the payload means "not needed" and never
  "invented", and that the current lands must be re-read at submit and retry time so an added,
  edited, or removed land is reflected without exposing anything new.

## Land clarification

- **MUST**: a land clarification (`needs_land_clarification`) MUST be decided by the service — never by
  the client — and offered only when the request is `mode: all_active` with two or more lands whose
  known attributes disagree with a retrieved candidate's `applicability`; `general`, a single land, and
  a `selected` request MUST delegate to the accepted answer/abstention path and MUST never be asked to
  clarify again (a `selected` request is a person who has already chosen). A clarification payload MUST
  be exactly the accepted `AskResponse` keys with `answer: ""`, `sources: []`, and a non-empty unique
  list of the request's own opaque land ids; it MUST NOT carry a passage, excerpt, figure, date, or a
  `crop`-based distinction (the request has no crop field), and an omitted/`unknown` land attribute
  MUST never exclude a candidate or be given an invented value. The client MUST resolve `land_ids_to_choose`
  against the local list, show the lands' **saved names and known attributes** (never invent, rename, or
  reorder a land; ignore a returned id it does not store) and, on the person's choice, resubmit the
  **exact original wording** as `mode: selected` over only the chosen local ids with only the needed
  attributes (a chosen land no longer stored degrades to the accepted `general` request) while appending
  **no second user message**. Reason: `land_clarification` established that the service alone knows the
  retrieved source applicability (so the trigger cannot live in the client), that a person must never be
  asked to choose when only one land exists or after they already chose, and that the whole point of the
  feature — the assistant asking instead of guessing one land — is lost if the client fabricates a land,
  loses the person's wording, or dresses the question up as a new one.

## Client land scope

- **MUST**: every assistant entry MUST render only the `land_scope` its own decoded response carried,
  copied at the single creation site `ChatHomeState.ResponseReceived` (never from
  `lastResponseStatus`), and that caption MUST state in plain Spanish which lands were taken into
  account (`general` / all lands / the chosen lands) while MUST NOT naming a land or an id, implying
  that land details prove eligibility, adding a confident or success affordance, or appearing on a
  failed request or a clarification. Reason: `answer_land_scope` established that a person must be
  able to tell at a glance whether an answer used none, all, or the chosen lands without ever being
  told their land's details prove they qualify; `chat_accessibility` renders this transcript next.

## Land data disclosure

- **MUST**: the on-screen data-handling notice MUST describe only the current behaviour — the lands
  are saved device-locally, and a question sends the question as written plus, for a land-aware
  answer, each land's opaque id and only the needed `municipality`/`water_regime`/`production_method`
  (an unknown value sent as `unknown`, name/notes/area/timestamp never sent). It MUST NOT promise
  backup, a cloud copy, or confidentiality beyond what the answer service's own terms offer, and
  MUST NOT name a land, an id, or make any eligibility or legal claim. Its sendable-attribute list
  MUST stay pinned (`privacy/LandDataDisclosure.kt`) and tied to the real encoded payload by a test,
  so adding a sendable dimension fails until the notice is updated. Reason: `land_data_disclosure`
  established that a person must be able to trust the plain-Spanish notice to match what the app
  actually does, so over-promising a backup or under-describing the payload is the failure to avoid;
  `chat_accessibility` audits the surface next.

## Chat accessibility

- **MUST**: the chat surface MUST keep plain-Spanish text on every control and transcript entry (never
  an unnamed button), one `mergeDescendants` node per transcript entry reading its `Tú`/`Asistente`
  label, scope caption, optional state label, and body, and every newly appended assistant reply —
  `answered` as well as `abstained` — a `LiveRegionMode.Polite` node (a `Tú` entry is never
  announced as a reply, and the failure notice MUST stay a polite live region that does not merge its
  retry control, so `Reintentar` remains its own focusable node). It MUST NOT convey any state by
  colour alone, MUST keep a visible focus indication on its controls (Material's default indication,
  or a shared outline that keeps it — never remove it), MUST NOT override Material's minimum
  interactive size (no `LocalMinimumInteractiveComponentSize`), MUST bring the newest transcript
  element (entry, working notice, failure notice, or chooser) into view once per appended element
  without moving the composer's text or focus and without jumping to the page bottom, MUST keep the
  capped content column centred instead of stretched, and MUST NOT render the clarification chooser's
  "no puedo mostrar tus terrenos" fallback before the guarded local read resolves (an unresolved read
  shows only the title and explanation). Reason: `chat_accessibility` established the first
  accessibility baseline for this surface, and a later feature can silently regress a control's name,
  an entry's merged node, an announcement, a target size, or the scroll timing without any test
  failing.
