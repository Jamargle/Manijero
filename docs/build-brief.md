# Build Brief — Agricultural Assistant

## Problem

Olive growers (aceituneros) in Jaén have traditionally relied on paper-based processes and specialists (often cooperative advisors) to handle agricultural bureaucracy, PAC regulations, and government aids. As these processes slowly digitalize, farmers lack proper training on the new tools and remain dependent on specialists. The "Agricultural Assistant" app aims to reduce this dependence by providing an AI-powered conversational assistant that answers questions about official regulations, using only verified official documents as source.

## Users

- **Primary: Olive growers (aceituneros)** in Jaén with small parcels (20-150 olive trees per parcel). Mostly small-scale farmers with limited tech knowledge. The primary user profile is Spanish-speaking with colloquial language, limited formal training, and who currently delegate most paperwork to their cooperative. They use mobile phones but are not computer-literate. The best tester is the person who has the least ease of use with mobile phones.

- **Secondary: Cooperative advisors** who currently handle paperwork for farmers. Not currently available; collaboration will be offered after demo.

- **Tertiary: Technical specialists** (not in MVP scope).

## Goals

1. **Provide accurate answers** about PAC, BOE, BOJA, FEGA regulations based exclusively on official documents.
2. **Reduce dependence** on specialists for basic inquiries about deadlines, requirements, and procedures.
3. **Be accessible** to farmers with basic smartphone knowledge — large buttons, high contrast, plain Spanish, few screens.
4. **Say "I don't know" reliably** when information isn't in the verified corpus, with helpful referral to cooperative or agricultural extension office.
5. **Maintain budget ≈ 0 €** using only free-tier services and local processing where possible.

## Non-Goals (for MVP)

- Parcel management, wages, fertilizers, income, and expenses
- User accounts and login/register
- Document upload or letter photos
- Semi-automatic Knowledge Ops (Scouts, automatic reindexing)
- iOS support
- Voice input (STT)
- Agent with tools or AI Advisor
- Personalized amount calculation
- Google Play integration

## MVP Slice

The vertical slice that proves the riskiest useful behavior:

- **Chat interface** where farmers can type or select suggested questions
- **Profile selection** (first screen): "Mi olivar es: secano / regadío / los dos" and "Producción: convencional / ecológica" — stored locally on device, no user account
- **Hybrid search**: ChromaDB (vector) + BM25 (lexical) with RRF fusion
- **Filters**: profile (2-touch), campaign, valid=true
- **Threshold check**: If similarity below minimum → "No lo sé" without calling LLM
- **LLM generation**: Gemini Flash T=0, temperature=0, top_p=1, structured JSON response `{found, answer, sources}`
- **Citations**: Numbers [1], [2]... referencing chunks with numbered context
- **Legal notice**: "Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional."
- **Verification date**: "Documentos verificados por última vez dd/mm/aaaa"
- **Fallback**: If found=false → fixed message: "No he encontrado esta información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."
- **Critical mode**: For `critico:true` topics → extractive mode with literal snippet, source, and date

## Core Domain Concepts (from CONTEXT.md)

- PAC, PEPAC, Solicitud única, SIGPAC, FEGA, MAPA, BOE, BOJA
- RAG, BM25, RRF, hit@k, Grounding, Extractive mode
- 2-touch profile (secano/regadío + convencional/ecológica)
- Campaña, critico, vigente, valid_until
- Golden dataset, quality gates

## Technology Constraints

- **Framework**: Kotlin Multiplatform + Compose Multiplatform
- **Targets**: Android + Desktop (JVM); no iOS in MVP
- **LLM**: Gemini Flash (fixed model), free tier
- **Embeddings**: bge-m3 local (requires >20 GB RAM server)
- **Vector DB**: ChromaDB, free, serverless
- **Lexical search**: BM25 with rank_bm25
- **Reranker**: Optional, bge-reranker-v2-m3 local (only if eval improves)
- **Parsing**: pymupdf4llm (PDF→Markdown); Docling (tables); Tesseract (Spanish OCR)
- **Chunking**: By legal structure (Article, Chapter, Annex); 500-800 tokens, 10-15% overlap; contextual prefix `[Regulation · Chapter · Article]`
- **Backend**: Python 3.11 + FastAPI with endpoint POST `/ask`
- **Client**: Ktor Client, `kotlinx.serialization`
- **Hosting**: Self-hosted server + Docker Compose + Cloudflare Tunnel (free tier)
- **CI/CD**: GitHub Actions (lint, pytest, contract tests, build, caches)
- **Observability**: Langfuse self-hosted (Docker) or SQLite
- **Tests**: kotlin-test, MockEngine, Compose UI tests, quality in CI
- **Budget**: ≈ 0 €, all free and migratable via interfaces in case the product scales

## Discovery Questions (Open)

1. What is the exact structure of the catalog of official documents? (We have catalogo.csv with 10 seed documents, but structure may evolve.)
2. How should the "campaign" field be handled? (Auto-injected per question, or user-selected?)
3. What is the exact format for the legal notice and verification date? (User testing needed.)
4. Should the 2-touch profile be selectable on first run only, or every time the app opens?
5. What happens when the free tier of Gemini changes or ends? (Migration plan needed.)
6. How will the corpus be kept up to date after MVP? (Semi-automatic Knowledge Ops?)

## Success Criteria (for MVP)

- ✅ hit@5 ≥ 85% on golden dataset (minimum 40 questions)
- ✅ Correct abstention on trap questions: 100% (no hallucination)
- ✅ Fidelity (judge) ≥ 95%
- ✅ 0 invented numbers/dates in golden dataset
- ✅ p95 latency < 8 s
- ✅ Chat compiles on Android and Desktop
- ✅ 2-touch profile persistent on device
- ✅ Coverage screen shows which topics are covered and which are not
- ✅ Organic labeled "beta"
- ✅ Legal notices visible in responses with deadlines/amounts
- ✅ Citation quality: each source in sent context verified

## Risks and Open Questions (summary)

See `docs/risks-and-open-questions.md` for detailed risk register.

Last updated: 2026-10-05
