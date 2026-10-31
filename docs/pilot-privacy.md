# Pilot privacy: data flow, retention, and review gates

Status on 2026-10-31: **the qualified privacy/legal review has not happened.** The committed
review record (`backend/config/pilot_privacy_review.json`) is `pending`, so the pilot gate
and the separate Gemini gate are closed. Nothing in this repository claims that the design
below is lawful, compliant, approved, or ready for real users. Recording a review is a human
decision outside the implementation; see "Recording the review" below.

Owner: `pilot_privacy_readiness` ([spec](specs/pilot_privacy_readiness.md)). Operator commands
are in [`backend/README.md`](../backend/README.md) ("Product-improvement retention and the
privacy gate").

## Data-flow inventory

| Step | Where | What is processed | What is kept, and for how long |
|---|---|---|---|
| Land records | Android/Desktop app, device-local store | Every saved land field (name, zone, municipality, variety, surface, trees, notes, timestamps) | On the device, plus up to three same-device automatic copies; never sent. Android excludes them from OS backup/transfer. |
| Question | App → managed tunnel (TLS edge) → loopback API | The question as written; for a land-aware answer, each active land's opaque id and only the needed `municipality`/`water_regime`/`production_method` (unknown as `unknown`) | The app keeps the transcript in memory for the session. The API keeps nothing unless retention applies (below). The tunnel provider terminates TLS and therefore processes the request; its handling is governed by its own terms, which are part of the pending review. |
| Retention choice | App → API, field `retain_for_improvement` | A boolean, sent only as `true` when the person ticked the box for that one send; otherwise absent | Not stored by itself. |
| Answer | API → app | Answer text, cited official sources, scope | Not stored by the API unless retention applies. |
| Request metadata log | API stdout → systemd journal (pilot profile only) | Method, path, status, duration, gate, time; plus fixed retention/error codes | Journal retention is set by the host (no value configured in this repository). Never contains question, answer, land values, client id, or token. |
| Product-improvement retention | API → owner-only SQLite file (`MANIJERO_RETENTION_DB`), only when configured **and** opted in | Redacted question and redacted final answer (answered or abstained), answer state, UTC creation date, expiry date | Deleted no later than 30 days after creation (see below). No land context, land id, municipality, client id, token, IP address, device id, or precise time. |
| Owner export | Owner command → owner-only file outside the repository | The unexpired redacted records | Outside the automatic purge: the owner must delete an export within the same 30-day window. |
| Generation provider (Gemini) | Gated client implemented; no transport exists | Nothing is sent | The gates are closed and the repository ships no transport, so the provider stays extractive. When a reviewed change supplies one and every gate passes, the provider may receive only the redacted question and the reviewed excerpts of the cited candidates labelled by candidate number (`minimal_provider_payload`), never land context, names, notes, catalog ids, URLs, identifiers, or retained text. |
| Generation provider (local, Ollama) | API → Ollama on the same host, loopback `127.0.0.1:11434` only; off by default | When `MANIJERO_GENERATION_PROVIDER=local` and the matching `MANIJERO_LOCAL_MODEL` are set (and, in the pilot profile, the pilot review has passed — pending today): the same `minimal_provider_payload` as Gemini (redacted question plus the reviewed excerpts of the citation window), never land context, names, notes, catalog ids, URLs, identifiers, or retained text | The question stays on the host; nothing is sent off the machine and the app keeps nothing extra. The app logs only `provider=local` and a fixed outcome. Ollama's own server logs, model cache, and update checks are outside the app's control and are not configured by this repository. |

## Retention rules as implemented

- **Default off.** No store is opened unless `MANIJERO_RETENTION_DB` is set. Without the
  per-question opt-in, nothing is written even when a store exists.
- **Per question, separate from sending.** The chat composer shows an unchecked checkbox.
  Ticking it never sends. Every send (ask, retry, land choice) uses the current choice and
  then resets it, so each retained question needs a fresh tick. A clarification response is
  never retained.
- **Device-side exclusion.** If the wording contains a saved land's name, zone, municipality,
  custom variety, or notes, the app sends the question without the opt-in.
- **Server-side redaction** (`backend/app/redaction.py`): e-mail, web address, phone, DNI/NIE,
  IBAN, cadastral reference, SIGPAC-style or slash/colon-separated references (this also
  removes dates written as `30/04/2026`), polígono/parcela/recinto numbers, runs of six or
  more digits, names after "me llamo / mi nombre es / soy", capitalised names after land words
  ("finca", "cortijo", "olivar", …), and every land-context value in the request. If redaction
  or storage fails, nothing is retained and the answer is unchanged.
- **Known redaction limits.** Pattern-based redaction cannot recognise every personal detail:
  a name written in lowercase, without a trigger word, or in an unusual format; an address;
  a rare identifier format; or contextual details that identify someone indirectly can remain.
  The notice tells the person this and asks them not to write personal data.
- **Deletion.** A record's `expires_on` is its UTC creation date plus 29 days. Records whose
  expiry date is today or earlier are deleted before every write and by the daily
  `retention-purge` command; `retention-status` exits `1` (an alert) when any overdue record
  exists, and a failed purge exits `1`. Exports never include expired records.
- **Access.** The store must be in an existing directory with no group/other permissions,
  outside the repository; the file is created `0600`. Only the owner's operator commands read it.
- **Individual deletion.** Records carry no identifier of a person, so a single person's
  record cannot be found and deleted early; the owner can delete everything
  (`retention-delete-all --confirm`). Whether this is an acceptable deletion path is a question
  for the qualified review.

## Review gates

`backend/app/privacy_review.py` evaluates `backend/config/pilot_privacy_review.json`
(`pilot-privacy-review-v1`).

- **Pilot gate.** Passes only when `pilot_review.status` is `approved` or
  `approved_with_conditions` (with at least one condition), `reviewed_on` is an ISO date not
  in the future, `reviewer_qualification` is filled, `evidence_reference` is filled, and
  `scope` covers `data_flow`, `notice`, `opt_in`, `redaction_limits`, `retention_deletion`,
  `access_controls`, `incident_and_contact`, `host_terms`, and `tunnel_terms`. Otherwise
  `pilot_ops.py privacy-gate` and the pilot preflight report fixed blocker codes, and
  `serve_pilot.py` refuses to start (the preflight fails).
- **Gemini gate.** Additionally requires the pilot gate, its own dated qualified review over
  `model_terms`, `data_flow`, `data_sent`, and `retention_by_provider`, the exact reviewed
  `model` equal to `MANIJERO_GEMINI_MODEL`, `MANIJERO_GENERATION_PROVIDER=gemini`, and
  `data_sent` limited to `question` and `approved_passages`. The gated drafting path
  (`backend/app/gemini_generation.py`) also needs a recorded limits file
  (`backend/config/gemini_provider_limits.json`, committed all `null`) and an injected
  transport, which does not exist; so even when this gate passes, the service stays on the
  extractive, verifier-checked path. A model draft that fails any check falls back to it.
- The record keeps the reviewer's qualification, never their name or contact details.

## Recording the review (human step, not done)

1. A qualified privacy/legal reviewer assesses the applicable obligations, this inventory,
   the in-app notice (`Privacidad y ayuda` → "Si permites guardar una pregunta") and the chat
   opt-in copy, the redaction limits, retention/deletion and the individual-deletion
   limitation, access controls, the incident process and privacy contact, and current host,
   tunnel, and (separately) Gemini terms.
2. The owner records the dated outcome, conditions, qualification, and an evidence reference
   in `backend/config/pilot_privacy_review.json` through a reviewed change, and updates the
   notice copy if the reviewer requires it.
3. Open items that the review must settle and that this feature does not decide: the privacy
   and incident contact shown to participants, whether individual early deletion is required,
   the host journal retention period, and any change to the notice wording.
