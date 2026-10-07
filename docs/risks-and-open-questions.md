# Risks and Open Questions — Agricultural Assistant

This document tracks unresolved decisions, assumptions, risks, and research tasks. Review during the discovery quality gate (step 9 of the build-brief workflow).

## High Risks (🔴 Critical / 🔴 High)

### 1. Hallucinations regarding legal matters

| Prob. | Impact      | Mitigation                                                                               |
|-------|-------------|------------------------------------------------------------------------------------------|
| High  | 🔴 Critical | Validation cascade (7 checks), T=0, strict threshold, extractive mode, CI quality gates  |

**Details:** The LLM may invent legal dates, amounts, deadlines. The validation cascade (schema → citations → numeric grounding → semantic grounding → validity → policy) is the primary defense. If any check fails → `found=false` + fixed message.

### 2. Not knowing the domain (incomplete or poorly focused corpus)

| Prob. | Impact  | Mitigation                                                                                                                        |
|-------|---------|-----------------------------------------------------------------------------------------------------------------------------------|
| High  | 🔴 High | Domain Mapper + review by family as users + official documents as truth + measured coverage + scope screen |

**Details:** The seed corpus starts with 10 official documents. If the domain coverage is insufficient, users will get "no lo sé" too often. The Domain Mapper (task A13) proposes a taxonomy of procedures that the family validates. Coverage measured via golden dataset.

### 3. Confusing presentation deadline and modification deadline

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| High  | 🔴 High | Prompt rule 9, `critico:true`, extractive mode, specific golden dataset with questions about deadlines |

**Details:** Users frequently confuse "presentation deadline" (submitting a single request) with "modification deadline" (modifying after it has been submitted). The prompt has explicit rule 9: always distinguish between these two dates and state which campaign each refers to. The golden dataset includes specific trap questions on this.

### 4. Repealed regulation served as current

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🔴 High | BOE states, `valid_until`, re-check after generation, visible verification date, validity tests (RD 1077/2014) |

**Details:** RD 1077/2014 (SIGPAC) has been repealed since 1/1/2023, but it could appear if not filtered correctly. The system must mark `vigente=false` for repealed regulations and not use them to respond. Validity tests in CI verify this.

### 5. Erroneous or malicious document enters the corpus

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🔴 High | Whitelist of domains, human approval per PR, provenance (URL, hash, date), text treated as data never as instructions |

**Details:** Only white-listed domains: `boe.es`, `juntadeandalucia.es`, `fega.gob.es`, `mapa.gob.es`. PDFs treated as data, never instructions. Human approval required per PR. Provenance recorded (URL, hash, download date).

## Medium Risks (🟠 High / 🟠 Medium)

### 6. Official deadline different from the cooperative's internal deadline

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 High | Fixed closing line; do not respond regarding specific cooperative practices |

**Details:** The cooperative may have internal deadlines prior to the official ones. The code includes a fixed closing line: "Your cooperative may have internal deadlines prior to the official ones. Confirm with them." But it does not answer regarding specific practices of cooperatives.

### 7. The user acts solely based on what the bot says

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 High | Legal notice always visible and "consult with your cooperative" as standard closing |

**Details:** Risk that users take action solely based on bot output. Mitigation: legal notice always visible, standard closing "consult with your cooperative", and extractive mode that always displays the source.

### 8. Choosing non-applicable fragment (dryland vs irrigated, conventional vs organic)

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 High | Metadata `aplica_a`, 2-touch profile, case-based response |

**Details:** The system uses metadata filters (`aplica_a` in chunks, user profile) to show different answers for different profiles. But if the user selects the wrong profile or the metadata is incomplete, it may give inapplicable info. The 2-touch profile is the primary filter.

### 9. Validation bias (everything validated with conventional profile)

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 Medium | Ecological segment labeled "beta" explicitly; expand with neighbors and official FAQs; cooperative review after demo |

**Details:** The golden dataset and validation metrics may be biased toward the conventional profile (A and B segments). Mitigation: ecological segment labeled "beta" explicitly, efforts to add FAQs for ecological users post-MVP, and review by cooperative after demo.

### 10. Change or reduction of Gemini free tier

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 Medium | Fixed model, `LLMClient`, fallback, cache, migration to paid tier |

**Details:** Free tier conditions can change (Google may use inputs/outputs for model improvement, reviewers may read them). Mitigation: model fixed in config, `LLMClient` with fallback chain (Gemini → Groq/OpenRouter → local Ollama → saturation message), semantic cache, per-device limit, migration plan to paid tier if there are real users.

### 11. Privacy: questions sent to a Gemini free tier

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 Medium | No personal data, PII filter, privacy notice, migration to paid tier if real users exist |

**Details:** Gemini free tier may use inputs/outputs for model improvement and reviewers may read them. Mitigation: never send personal data, PII filter before sending to LLM, privacy notice in the app, process sensitive material locally (Ollama) when possible.

### 12. Personal data in notices, letters, or listings

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 Medium | Anonymize, process locally, do not upload to Git, do not index nominal listings |

**Details:** Cooperative notices may contain personal data (names, license plates). Must be anonymized before indexing. Process locally (Ollama). Discard if personal data detected. Never upload to Git or index nominal listings.

### 13. Scanned PDFs or broken tables

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 Medium | Docling/OCR, manual review of key tables, snapshot tests |

**Details:** Some official PDFs may be scanned documents or have broken tables. Mitigation: Docling for tables, Tesseract OCR for scans, manual review of key tables, snapshot tests of parsing ~10 real PDFs.

### 14. Scope creep (Knowledge Ops grows out of control)

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| High  | 🟠 High | Semi-automatic version in core; full autonomy in weeks 5-6 |

**Details:** Knowledge Ops (Scouts, classification, etc.) may grow beyond control in the core. Mitigation: semi-automatic version in the core (weeks 0-4), full autonomy planned for weeks 5-6. Pipeline version and its dependencies versioned in Git.

## Lower Risks (🟡 Medium)

### 15. Conflicts between development agents

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟡 Medium | Contracts first, one lane per directory, PR + CI |

**Details:** Multiple lanes (A-G) working in parallel. Mitigation: contracts first (openapi.yaml, JSON schemas), one lane per directory, merge via PR only, CI is the referee.

### 16. False sense of authority

| Prob. | Impact | Mitigation |
|-------|---------|-----------|
| Medium | 🟠 Medium | "Guidance", literal source, date, declared scope |

**Details:** Users may trust the bot too much. Mitigation: always label responses as "guidance information", always show source and date, say "I don't know" when there is no certainty, and visible legal notice.

## Open Questions (pending decisions)

| # | Subject | Required decision | When |
|---|---------|-------------------|------|
| P1 | Exact structure of `catalogo.csv` | Define mandatory fields and examples | Week 0-1 |
| P2 | Handling future campaigns | What happens when campaign 2027 starts; is a new corpus added automatically? | Week 1 |
| P3 | LLM fallback strategy | Exact chain: Gemini → Groq/OpenRouter → local Ollama → message | Week 0-1 |
| P4 | Exact legal notice format | Variants and A/B testing with family | Week 1 |
| P5 | Initial similarity threshold | Numerical value for hit@5 ≥ 85% | Week 0-1 |
| P6 | Response cache mechanism | By hash (prompt + context + model version) | Week 0 |
| P7 | On-device profile format | SharedPreferences vs SQLite vs JSON file | Week 0 |
| P8 | OCR strategy for scanned PDFs | Tesseract Spanish config, thresholds | Week 1-2 |
| P9 | Paid migration strategy | Real user threshold justifying paid Gemini/Claude | Before release |
| P10 | Validation of Law 39/2015 | Confirm it is the regulation governing common administrative procedure | Week 1 (A1.3) |
| P11 | Relevance of aid 6613 | Check relevance for the family's municipality | Week 1 |
| P12 | Reranker: enable or discard | Decision based on colloquial subset metrics | Week 3 |
| P13 | Offer collaboration to cooperative | After demo, what exactly to offer | After week 4 |
| P14 | Actual available hours/week | Real estimation for planning | Week 0 |
| P15 | Olive grower calendar (optional) | Whether to include in MVP or not; content and design | Week 3-4 |

## Recently Resolved (for reference)

- **RD 1077/2014 repealed**: Confirmed repealed since 1/1/2023 by repeal provision of RD 1047/2022. Indexed as `vigente=false` only for testing.
- **Voluntary digital notebook**: RD 1054/2022 made it temporarily voluntary until the next PEPAC (from 2027). Identify modifying RD.
- **Presentation vs modification**: 2026 presentation deadline: Feb 1 - Apr 30. Modification deadline extended until Jun 15, 2026 (FEGA Resolution 05/20/2026). Previously fixed on May 31.
- **Outdated notice**: A cooperative notice gave a deadline "when sent" and may have become outdated. This is why campaign, `valid_until`, injected today's date, and visible verification date are needed.

Last reviewed: 2026-10-05
