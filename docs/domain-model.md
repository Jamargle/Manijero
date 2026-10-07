# Domain Model — Agricultural Assistant

This file defines the domain entities, relationships, states, and lifecycle rules for the project.

## Entities

### 1. User Profile

| Field                      | Type      | Description                                                             |
|----------------------------|-----------|-------------------------------------------------------------------------|
| `prefix_dry`               | Boolean   | `true` if the parcel is dryland                                         |
| `prefix_irrigated`         | Boolean   | `true` if the parcel is irrigated                                       |
| `prefix_dry_and_irrigated` | Boolean   | `true` if the user wants to see both options (dryland/irrigated)        |
| `prefix_organic`           | Boolean   | `true` if production is organic                                         |
| `prefix_non_organic`       | Boolean   | `true` if production is conventional                                    |
| `selected_profile`         | String    | Stored value: "dryland", "irrigated", "both", "conventional", "organic" |
| `selection_date`           | LocalDate | When the profile was selected (stored on device)                        |

**Invariants:**

- Only one profile can be selected at a time (unless `prefix_dry_and_irrigated=true`)
- If the user is organic, the profile includes specific EU considerations
- The profile is stored locally; there is no user account in the MVP

### 2. Question

| Field                | Type      | Description                                                                              |
|----------------------|-----------|------------------------------------------------------------------------------------------|
| `id`                 | String    | Unique ID (hash of normalized prompt)                                                    |
| `original_question`  | String    | Question as written by the user (colloquial)                                             |
| `rewritten_question` | String    | Question rewritten with official terms (after glossary)                                  |
| `profile`            | String    | Filtering context: 2-touch profile                                                       |
| `campaign`           | String    | Current campaign (e.g. "2026") - injected by code, not LLM                               |
| `todays_date`        | LocalDate | Today's date - injected by code                                                          |
| `origin`             | String    | "user", "suggested", "trap"                                                              |
| `segment`            | String    | "A" (conventional, dryland), "B" (conventional, irrigated), "C" (organic), "transversal" |

### 3. Answer

| Field               | Type      | Description                                                               |
|---------------------|-----------|---------------------------------------------------------------------------|
| `found`             | Boolean   | `true` if information was found in the context                            |
| `answer`            | String    | Generated response (max. 1200 characters)                                 |
| `sources`           | List<Int> | Cited chunk indices [1], [2], etc.                                        |
| `verification_date` | LocalDate | When the document was last verified                                       |
| `legal_notice`      | String    | Fixed notice: "Información orientativa basada en documentos oficiales..." |

### 4. Chunk

| Field              | Type         | Description                                                   |
|--------------------|--------------|---------------------------------------------------------------|
| `id`               | Int          | Unique numeric ID                                             |
| `text`             | String       | Snippet content (clean text, no headers/footers)              |
| `doc_id`           | String       | Source document identifier (e.g. "rd_1048_2022")              |
| `title`            | String       | Title or name of the regulation                               |
| `organism`         | String       | MAPA, BOE, BOJA, FEGA, etc.                                   |
| `article`          | String       | Article, chapter, annex                                       |
| `page`             | Int          | Page number (if applicable)                                   |
| `publication_date` | LocalDate    | When originally published                                     |
| `original_url`     | String       | URL of original published text                                |
| `consolidated_url` | String       | URL of consolidated text (informative)                        |
| `valid`            | Boolean      | `true` if regulation is still current today                   |
| `valid_until`      | LocalDate    | Until when valid (if applicable)                              |
| `campaign`         | String       | Campaign it applies to (e.g. "2026")                          |
| `critico`          | Boolean      | `true` if it includes critical deadlines, amounts, thresholds |
| `modifies`         | List<String> | IDs of regulations this modifies                              |
| `repeals`          | List<String> | IDs of regulations this repeals                               |
| `supersedes`       | List<String> | IDs of regulations this supersedes                            |

### 5. Catalog Entry

| Field              | Type      | Description                                       |
|--------------------|-----------|---------------------------------------------------|
| `doc_id`           | String    | Unique identifier (e.g. "rd_1048_2022")           |
| `title`            | String    | Regulation title                                  |
| `organism`         | String    | Issues the regulation                             |
| `url`              | String    | Two URLs: original published and consolidated     |
| `publication_date` | LocalDate | When published                                    |
| `valid`            | Boolean   | Current validity status                           |
| `campaign`         | String    | Associated campaign                               |
| `critico`          | Boolean   | If it includes critical data (deadlines, amounts) |
| `notes`            | String    | Additional metadata                               |

## Relationships

```
User Profile --(profile)--> Question (filters: profile, campaign, today's date)
Question --(rewritten)--> Question (rewritten_question for search)
Question + Chunks --> Answer (RAG pipeline: hybrid search → threshold → LLM)
Answer --> User (with citations, legal notice, verification date)
Chunk --(belongs_to)--> Catalog Entry
Catalog Entry --(versioned)--> Historical versions (modifies, repeals, supersedes)
```

## State Transitions

### User Profile State

```
No profile --> User selects profile --> Profile stored locally
Profile stored --> App opens with profile pre-selected
Profile can be changed anytime --> New profile stored, replacing previous
```

### Document / Chunk State

```
New official document published (BOE/BOJA/FEGA)
    ↓
Scout discovers and downloads
    ↓
Parser: PDF → Markdown → Chunks with metadata
    ↓
Chunker: legal structure, contextual prefix, metadata (valid, campaign, critical)
    ↓
Indexed into ChromaDB + BM25
    ↓
Available for search
    ↓
Vigencia Checker verifies state
    ↓
If repealed/modified: update valid=false, add metadata
    ↓
Reindex: makeover + BM25 rebuild
    ↓
Available in app with updated status
```

### Answer State

```
User submits question
    ↓
System rewrites colloquial → official terms
    ↓
Hybrid search (Chroma + BM25 + RRF) with filters
    ↓
Threshold check
    │
    ├──↓ Similarity ≥ threshold: LLM generation
    │     ↓ JSON structured answer {found, answer, sources}
    │     ↓ Add verification date + legal notice
    │     ↓ Return to user
    │
    └──↓ Similarity < threshold: "No lo sé" (without calling LLM)
          ↓ Fixed message + referral to cooperative
          ↓ Return to user
```

## Constraints

### Data Constraints

- **No PII** in any stored data (profile is anonymous: only dryland/irrigated +
  conventional/organic)
- **Profile never leaves device** - stored in SharedPreferences / localStorage
- **campaign** always injected by code, never by LLM
- **today's date** always injected by code, never by LLM
- **valid** determined by system, not by LLM
- **valid_until** from metadata, if applicable

### LLM Prompt Constraints

- **temperature=0, top_p=1** - deterministic responses
- **bounded max_tokens** - max 1200 characters in answer
- **Structured JSON output** `{found, answer, sources}` - no additional text
- **Numbered context** `[1]...[8]` for code verification
- **Plain language** - short sentences, no jargon, numbered steps
- **Extractive mode** in `critico:true` - includes literal snippet, source, and date
- **Delegation rules** by code: explain what the procedure is, what the user contributes, and what
  to consult with their cooperative
- **Fixed lines by code** added:
    - "Información orientativa basada en documentos oficiales. No sustituye el asesoramiento profesional."
    - "Tu cooperativa puede tener plazos internos anteriores a los oficiales. Confírmalo con ella."
      (on responses with deadlines)
    - "Documentos verificados por última vez el dd/mm/aaaa."

### Search Constraints

- **Metadata filters**: profile (`aplica_a`), campaign, `valid=true`, `valid_until` after today's
  date
- **Hybrid search**: vector (Chroma) + BM25 (acronyms: SIGPAC, DUN, eco-scheme). Fusion with RRF.
- **Minimum similarity threshold** calibrated with golden dataset. If not exceeded: fixed response
  "No lo sé" without calling LLM.
- **Today's date and campaign injected** in the prompt - LLM has no clock.

## Lifecycle Rules

1. **Document publication**: When an official norm is published (BOE, BOJA, FEGA), it enters the
   system via Scout → Parser → Chunker → Index → Vigencia Checker.

2. **Vigency update**: When a norm is modified or derogated, the Vigencia Checker updates `valid`
   metadata. Human approval required for additions/changes (per D11: "adding or changing requires
   approval").

3. **Index rebuild**: When metadata changes, `make reindex` regenerates ChromaDB and BM25 index from
   catalogo.csv.

4. **Question answering**: User submits question → rewriting → hybrid search → threshold → LLM →
   answer with citations + legal notice + verification date.

5. **Feedback loop**: User 👍/👎 with motive → frequent "No lo sé" → task for Scouts or new golden
   dataset question.

## Glossary (subset of CONTEXT.md)

- **RAG** - Retrieval-Augmented Generation
- **hit@k** - Proportion of questions whose correct source appears among the first k results
- **Grounding** - Ensuring every claim is supported by the context
- **Extractive mode** - Displaying the literal document snippet
- **Golden dataset** - Questions with verified answer and source
- **Quality gate** - Metric threshold for merging changes
- **2-touch profile** - dryland/irrigated + conventional/organic
- **critico** - Topic with critical deadlines, amounts, thresholds
- **campaign** - Aid season (e.g. 2026)
- **valid** - Regulation is still current today
- **valid_until** - Date until which it is valid
