# CONTEXT.md — Glossary and Domain Language

This file contains the canonical terms and domain language for the project. Use these precise terms in all project documentation, prompts, code comments, and agent instructions.

## Core Domain Terms

| Term | Definition |
|------|-----------|
| **PAC** | Common Agricultural Policy (EU) |
| **PEPAC** | Strategic Plan of Spain's PAC 2023-2027 |
| **Solicitud única** | Annual application integrating direct aid and other PAC aids |
| **SIGPAC** | Geographic Information System of Agricultural Parcels |
| **FEGA** | Spanish Agricultural Guarantee Fund |
| **MAPA** | Ministry of Agriculture, Fisheries and Food |
| **BOE** | Official State Gazette |
| **BOJA** | Official Gazette of the Junta de Andalucía |
| **ELI** | European Legislation Identifier: stable URL of a regulation |
| **Texto consolidado** | Updated version of a regulation; in BOE it is informative and without legal value |
| **RAG** | Retrieval-Augmented Generation: retrieve chunks and generate response using only them |
| **BM25** | Lexical word search |
| **RRF** | Reciprocal Rank Fusion: ranking fusion |
| **hit@k** | Proportion of questions whose correct source appears among the first k results |
| **Grounding** | Ensuring every claim is supported by the context |
| **Extractive mode** | Displaying the literal document snippet along with the explanation |
| **Golden dataset** | Set of questions with verified answer and source, used for evaluation |
| **Quality gate** | Metric threshold a change must pass to be merged |
| **Ports and adapters** | Pattern isolating external services behind interfaces |
| **Domain Mapper** | Agent that reads official guides and proposes procedure taxonomy |
| **Scout** | Agent that discovers candidates from their source (BOE, BOJA, Web) |
| **Classifier** | Agent that determines relevance and topic (JSON, T=0, confidence) |
| **Vigencia Checker** | Agent that verifies BOE states, "is repealed" patterns, valid_until |
| **2-touch profile** | How the user identifies: dryland/irrigated / both and conventional/organic |
| **Campaña** | Season/aid period (e.g., 2026 campaign) |
| **critico** | Mark indicating a topic includes critical deadlines, amounts, thresholds; mandatory extractive mode |

## User Types

| Role | Description |
|------|-----------|
| **Farmers/aceituneros** | End users: Jaén olive growers with small parcels (20-150 olive trees). Most delegate paperwork to the cooperative. 2-touch profile (dryland/irrigated, conventional/organic). Colloquial language, low technical training. |
| **Cooperative advisor** | Cooperative staff currently handling paperwork for farmers. None available yet; collaboration will be offered after demo. |
| **System** | The RAG + LLM + backend stack that processes questions and returns answers based on official documents. |

## Key Constraints

| Constraint | Value                                                                                                                                                   |
|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Target surface** | Olive groves in Jaén, parcels of 20-150 olive trees (order of magnitude: tenths of a hectare to a bit more than one)                                    |
| **Dryland/Irrigated** | There are dryland and irrigated lands. The 2-touch profile allows selecting both.                                                                       |
| **Production** | Conventional and organic. The 2-touch profile includes both.                                                                                            |
| **Interface language** | The app is implemented in English (code/UI structure), but users use Spanish (colloquial, with sector jargon).                                          |
| **No user accounts** | MVP does not include login/register. The 2-touch profile is stored locally on device.                                                                   |
| **Budget** | ≈ 0 €: all free but migratable in case product scale.                                                                                                   |
| **LLM** | Gemini Flash (model fixed in config), free tier.                                                                                                        |
| **Embeddings** | bge-m3 local, free (server with >20 GB RAM).                                                                                                            |
| **Vector DB** | ChromaDB, free, serverless.                                                                                                                             |
| **DOMAIN** | Official documents only: BOE, BOJA, FEGA. Do not index nominal listings, cooperative notices as content, or free web search.                            |
| **Privacy** | No personal data. PII filter before sending to LLM and before recording logs. Process sensitive material locally (Ollama), never with Gemini free tier. |
| **Legal notice** | "Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional." Always visible in responses with deadlines or amounts.        |

## Language Guidelines

- **Respond exclusively with retrieved context information**
- **If not found: "No he encontrado esta información en los documentos oficiales que tengo. Te recomiendo consultar con tu oficina comarcal agraria o con tu cooperativa."**
- **NEVER invent dates, deadlines, amounts, percentages, requirements, or article numbers**
- **Cite with [1], [2]... and include source and date**
- **Plain language: short sentences, no legal jargon, no technology jargon**
- **If snippets contradict each other: notify the user**
- **Extractive mode on critico:true topics: include literal snippet, source, and date**
- **Standard closing: "Tu cooperativa puede tener plazos internos anteriores a los oficiales. Confírmalo con ella."**
- **Documents last verified mm/dd/yyyy**

## MVP Scope Markers

- **✅ IN MVP:** RAG chat with cited sources, verification date, legal notice; 2-touch profile; suggested questions; coverage screen; "No lo sé" responses with cooperative referral; 0 € budget; Gemini Flash free tier; ChromaDB + local BM25; Kotlin Multiplatform Android + Desktop.
- **❌ OUT OF MVP:** Parcel management, wages, expenses; user accounts and login; document upload or photos; semi-automatic Knowledge Ops; iOS; voice input; agent with tools.

Last updated: 2026-10-05
