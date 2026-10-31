# Manijero Durable Constraints

Operational MUST/MUST NOT rules that future features have to respect on top of
`AGENTS.md`, `CONTEXT.md`, `DESIGN.md`, and the accepted contracts.

The rules live in one file per area so a feature reads only the areas it touches. A
reference to "`CONSTRAINTS.md`, section X" means the section of that name in the file
listed below.

| File | Sections |
|---|---|
| [`docs/constraints/answers-and-knowledge.md`](docs/constraints/answers-and-knowledge.md) | Answer grounding, Local embeddings, Hybrid retrieval, Abstention, Safety evaluation, Campaign scope, Coverage disclosure, Knowledge updates and retrieval |
| [`docs/constraints/client-chat.md`](docs/constraints/client-chat.md) | Client request failure, Client response states, Client source cards, Client land context, Land clarification, Client land scope, Land data disclosure, Chat accessibility, Chat surface presentation |
| [`docs/constraints/lands.md`](docs/constraints/lands.md) | Land editing, Land fields and storage, Land automatic copies, Land list search and summary, Land removal, Land form accessibility |
| [`docs/constraints/ui-shell.md`](docs/constraints/ui-shell.md) | Brand vectors, Shared component layer, App shell and navigation |
| [`docs/constraints/hosting-and-pilot.md`](docs/constraints/hosting-and-pilot.md) | Hosted pilot and provider boundaries |

Adding a rule: put it under the matching section of the matching area file (see the writing
budget in `.agents/skills/feature-implementer/references/implementation-rules.md`). Add a new
section or area file only for a new area, and list it in this table.
