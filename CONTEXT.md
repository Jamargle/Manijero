# CONTEXT.md — Project Glossary and Product Constraints

Use these terms consistently across product and engineering documents. This is a glossary and stable context, not a roadmap.

## Domain terms

| Term | Definition |
|---|---|
| Olive grower / land manager | Person who owns or manages one or more olive-growing lands |
| Land | A user-managed olive-growing area represented in the app; not necessarily a legal cadastral parcel |
| Zone / paraje | The plain-language place, path, or area that identifies where a land is; required on every saved land, never inferred |
| Variety | The olive variety chosen from the approved shortlist, a short custom `Otra` text, or not yet known |
| Surface | Optional user-entered land area in hectares; absent stays absent, never a zero or a guess |
| Tree count | Optional user-entered number of olive trees; a whole number of at least one |
| Water regime | Whether a land is dryland, irrigated, mixed, or not yet known |
| Production method | Whether production is conventional, organic, mixed, or not yet known |
| PAC | Common Agricultural Policy of the European Union |
| PEPAC | Spain's Strategic Plan for the PAC |
| Solicitud única | Annual application that combines direct aid and other PAC aid |
| SIGPAC | Geographic Information System for Agricultural Parcels |
| FEGA | Spanish Agricultural Guarantee Fund |
| MAPA | Spain's Ministry of Agriculture, Fisheries and Food |
| BOE / BOJA | Spain's Official State Gazette / Official Gazette of Andalusia |
| RAG | Retrieval-Augmented Generation: retrieve source passages, then generate a response grounded in them |
| Abstention | A clear response that the assistant cannot answer safely from available evidence |
| Source-anchored question | Evaluation question with a reviewed expected answer and authoritative source |

## Users and interaction

- **Primary audience:** people with little computer or app experience who own or manage one or multiple olive lands.
- **Language:** user-facing MVP copy and assistant responses are Spanish, using plain everyday language. Project documentation is English.
- **Accessibility baseline:** readable text, high contrast, large controls, short steps, clear recovery, and no unexplained technical terms.
- **Land context:** use all active lands by default; ask the user to choose when the answer materially differs by land. Unknown attributes remain unknown.
- **Privacy:** no account is assumed for MVP. Land records are local by default. Send only the minimum land context needed for a query and exclude personal data from telemetry.

## Product and platform constraints

- **MVP platforms:** Android and Desktop (JVM).
- **Future platform:** iOS is outside MVP delivery; implement business logic and Compose UI in shared `commonMain` so both can be reused later. Keep only platform integrations and entry points platform-specific.
- **Client:** Kotlin Multiplatform + Compose Multiplatform; keep platform-specific services behind narrow boundaries.
- **Answer sources:** approved official material for regulatory claims. A non-official or unverified source must not be presented as legal authority.
- **Budget:** near-zero is a goal/constraint, not a guarantee of ongoing free service. Provider terms, privacy, limits, and migration paths must be reviewed.

## Response principles

- Use only retrieved, approved evidence for factual legal claims.
- Do not invent dates, deadlines, amounts, thresholds, eligibility, or article numbers.
- Cite sources in a way a non-technical user can open and understand.
- Clearly distinguish a general explanation from what is known about the user's specific lands.
- If evidence is absent, ambiguous, expired, conflicting, or not applicable, say what is unknown and suggest a suitable human contact such as the cooperative or Oficina Comarcal Agraria.
- Critical amounts and deadlines need prominent source excerpts and dates.

## Scope markers

- **In MVP:** grounded AI chat, source display, abstention, basic multiple-land create/read/update/delete, land-aware clarification, Android and Desktop, local land storage, usability validation.
- **Out of MVP:** iOS release, account/cloud sync, shared ownership, precise parcel mapping, full farm/business management, document/photo upload, aid calculations, voice input, and unreviewed autonomous content ingestion.

Last reviewed: 2026-10-09
