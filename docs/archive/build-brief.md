# Build Brief — Olive Grove Assistant

## Product

A Kotlin Multiplatform app for people who own or manage one or more olive groves and have little experience with computers or apps. The MVP makes it easy to ask questions in plain Spanish and receive cautious, source-backed guidance about official agricultural rules and procedures. It also lets a person keep a simple local record of their groves so answers can account for their situation.

The MVP targets Android and Desktop (JVM). iOS is out of MVP release scope, but implement business logic and Compose UI in `commonMain` so iOS can later reuse both without rewriting product behavior. Keep only platform integrations and app entry points in platform-specific source sets.

## Users and problem

- **Primary users:** olive grove owners and managers, including people with several small or scattered lands. They may delegate paperwork to a cooperative and want to understand what applies, what to bring, and what questions to ask.
- **Access needs:** low digital confidence, everyday Spanish, short explanations, forgiving navigation, clear next steps, readable text, and large touch targets.
- **Validation:** test with the least digitally confident intended users. Family feedback can validate clarity and usability, not legal correctness.

## Product goals

1. Make asking an agricultural question easier than navigating official documents.
2. Give answers grounded in approved official sources, with citations, source dates, and an honest “I don't know” when evidence is missing.
3. Let people create and manage multiple olive lands with a small set of understandable details.
4. Use land context when relevant; consider all of a user's lands by default and ask which land they mean when answers materially differ.
5. Keep the interaction usable for people who are not comfortable with computers.

## MVP scope

The MVP is one complete journey: set up a local land record (or several), ask a question in plain Spanish, receive a grounded answer that uses relevant land context, inspect its official sources, and correct land details later.

Included:

- Conversational assistant with typed questions and example prompts.
- Cited answers, source links, verification date, plain-language explanation, and explicit abstention when evidence is inadequate.
- Basic create, list, view, edit, and remove actions for multiple lands.
- Minimum useful land details: a name or nickname, municipality, dryland/irrigated status, and conventional/organic production. Area and notes may be included if they help answer an identified MVP question; avoid collecting precise identifiers by default.
- Local persistence on the device for land records and preferences; no account or cross-device sync is assumed for MVP.
- All-lands context by default, with a simple clarification choice when land-specific answers differ.
- Android and Desktop builds using shared Kotlin Multiplatform business logic and Compose UI.
- Accessible interaction basics: large controls, readable type, plain Spanish, visible progress, and recoverable errors.

## Explicitly out of scope for MVP

- iOS release or platform-specific iOS features (keep the shared layers ready for a later target).
- Accounts, cloud sync, collaboration, roles, or shared land ownership.
- Full farm management: tasks, workers, wages, expenses, inventory, machinery, yields, or accounting.
- Precise cadastral/SIGPAC parcel editing or mapping, document/photo upload, and personalized aid calculations.
- Voice input, autonomous agents, and automatic ingestion of unreviewed web content.
- Cooperative-specific practices as authoritative content.

## Answer policy

- Use approved official material only for legal or regulatory claims; every material claim must be traceable to its source.
- Never invent deadlines, amounts, eligibility, or article numbers. If evidence is missing, stale, contradictory, or does not match the user's land context, say so and provide an appropriate human referral.
- Keep the distinction between general guidance and professional advice clear. Critical dates and amounts need especially visible evidence and review.
- Land records help choose applicable context; they do not establish legal eligibility or replace an official application review.

## Technology direction

- Kotlin Multiplatform + Compose Multiplatform client; Android and Desktop are the MVP targets. Put business logic, presentation state, navigation, and Compose UI in shared `commonMain`. Put platform services and app entry points behind small platform-specific adapters; avoid Android/JVM-only types in shared code.
- Preserve shared Android/Desktop/iOS business logic and Compose UI, but do not spend MVP effort on iOS build/release, Apple-specific integrations, or iOS acceptance criteria.
- The existing Master Plan proposes a Python/FastAPI RAG service and official-document corpus. Treat model/provider and hosting choices as replaceable and validate them before release; land data must be minimized and protected in transit and in logs.
- The existing “approximately zero budget” assumption is a constraint to validate, not a promise that third-party free tiers are safe or permanent.

## Backend MVP completion slice

The backend is a separate FastAPI service for the same olive growers described above. Complete its local, contract-shaped answer path before public deployment: a request reaches `POST /ask`, uses a small reviewed corpus for Andalusia's PAC single application, and returns a grounded answer, a safe abstention, or a land clarification in the existing `AskResponse` shape. Current official sources map candidate coverage to the submission route, 2026 filing deadline, and 2026 modification deadline; an independent reviewer must approve the exact passages and published coverage statement before they become answer evidence. See [backend technical discovery](technical-discovery.md) and the [PAC corpus spec](../specs/backend_pac_corpus.md). `/health` remains a liveness check.

The slice composes the accepted offline catalog validation, retrieval, generation, abstention, and land-clarification rules into the HTTP path. It adds canonical reviewed source/passages and source-anchored evaluation cases; synthetic fixtures remain engineering tests, not evidence of legal coverage. Land scope and minimal-context rules stay aligned with the existing API contract and client constraints. Any generated draft must pass the code-owned grounding verifier before response assembly.

The first local route uses the existing extractive generator, with no hosted LLM. Reconsider a provider only after corpus coverage and the first measured baseline are reviewed; any later hosted model remains subject to provider terms, cost, data handling, and the code verifier. Keep current BM25 retrieval as the measurable baseline; add vector search or reranking only if reviewed evaluation shows a useful improvement.

**Included:** local `POST /ask`, contract and pipeline tests, a manually curated/reviewed initial corpus slice, report-only evaluation on source-anchored cases, and all three response states. **Deferred:** public hosting and deployment, Android/Desktop production wiring, `/feedback`, hosted-provider selection, automated knowledge scouts/ingestion, scheduled jobs, tracing infrastructure, nightly quality gates, and the optional reranker. This is the discovery plan, not a current task list; see [`backend/README.md`](../../backend/README.md), [`knowledge/README.md`](../../knowledge/README.md), and [`PROGRESS.md`](../../PROGRESS.md) for the implemented baseline and its limits.

Completion evidence is contract tests for all three response states, a reviewed corpus and critical passages, and a source-anchored evaluation report that states its coverage and gaps. No numeric quality gate is set before the first measured baseline is reviewed.

Visual design impact: none; this backend slice adds no user interface.

## MVP validation and success

Validate both usefulness and usability with realistic questions and people who have low digital confidence. Track:

- Whether a new user can add more than one land and later find/edit the right one without assistance.
- Whether questions are answered with relevant sources, or safely declined when evidence is inadequate.
- Whether a land-dependent question uses the correct context or asks a clear follow-up when needed.
- Retrieval coverage, citation correctness, unsupported-claim rate, and response time on a source-anchored evaluation set.
- User comprehension: can the person explain what the answer says, what it applies to, and where to get help?

Keep numerical thresholds in the evaluation plan and set them after the first measured baseline; do not treat inherited thresholds as verified performance.

## Assumptions and unresolved items

- Land records are device-local in MVP; backup, migration, and data loss recovery need an explicit stance before a real-user release.
- The exact land fields and whether area belongs in the first release should be validated against real questions and user comfort.
- Define behavior for an empty land list, unknown land attributes, conflicting land contexts, and an ambiguous “my grove” reference.
- Review the privacy, retention, and provider terms for questions sent to a hosted LLM before real-user release.
- The backend's source catalog and canonical passage set are empty. A human other than the author must review the initial source and critical excerpts before they become answer evidence; the reviewer and exact question coverage remain to be arranged.
- The first local `/ask` route uses extractive generation. Revisit provider selection only after reviewing corpus coverage and the first measured baseline.
- Existing design assets: no product design source found; the app icon is not a UI design system.
- Visual design direction: see [DESIGN.md](../../DESIGN.md).

Last reviewed: 2026-10-17
