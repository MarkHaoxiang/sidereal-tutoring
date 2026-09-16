# Architecture

Directus on Postgres is the system of record. Everything else reads and writes through it, and
nothing else holds durable state.

## Data flow

```
source                 ingester              documents row        generation job        artefact row
─────────────────────  ────────────────────  ───────────────────  ────────────────────  ──────────────────
.vtt / .srt / .txt  →  TranscriptIngester ┐
http(s) URL         →  WebPageIngester    ├→ DocumentDraft  →  documents            →  generation_jobs  →  homework
.pdf / .docx / .txt →  UploadIngester     ┘  (plain text)       (kind, status)          (queued→running      feedback
                                                                + student context        →succeeded|failed)   plans
```

A typst-format homework job: generate → template (house Typst wrapper) → compile (the typeset
service) → PDF uploaded to Directus files → `homework.pdf`.

- An ingester produces a `DocumentDraft` and nothing else; the caller writes the row. Ingestion
  and persistence are separated so an ingester can be tested with no Directus.
- A generation run is a `generation_jobs` row before it is anything else: its `input` replays
  it, its `model` and `generated_from` record provenance, its `status` and `error` are the
  outcome. A generation failure is a failed row, never a raised exception.
- A homework job also writes its questions as `questions` rows and records their ids in the
  homework's `generated_from`. It does not write the `homework_questions` junction.

## Who talks to whom

```
   browser ──── Directus SDK (tutor's session) ────────────────┐
      │                                                        │
      └──── /api/jobs (Directus bearer token) ──→ sidereal-app ┤
                                                               ├──→ Directus ──→ Postgres
   LLM agent ──── MCP (stdio) ──→ sidereal-mcp ────────────────┤
                                                               │
   sidereal-transcripts ──── Directus REST ────────────────────┘
```

- The frontend reads and writes domain rows through the Directus SDK directly — the app is not
  a CRUD proxy. It calls `/api` only for the one thing Directus cannot do: queue a generation.
- `sidereal-app` holds no credentials. Each request's own Directus bearer token builds its
  client, and `/users/me` validates it; Directus's permissions are therefore the only
  authorisation there is.
- `sidereal-mcp` is a second front door onto the same packages, so an agent has exactly the
  operations the app has. App and mcp never import each other.
- Rust services reach Directus over its REST API only — never the Postgres behind it, and never
  another service's store — so the database stays one owner's. `sidereal-typeset` is the
  exception: it reaches no Directus at all, and `sidereal-app` reaches it over HTTP to compile
  Typst homework.
- Directus's own admin app is the tutor's admin surface; generic CRUD screens are not rebuilt.

## Collections

Every collection has a `uuid` primary key and Directus's four audit fields (`date_created`,
`date_updated`, `user_created`, `user_updated`). Status and kind values are the lowercase tokens
below, and they must read the same in `directus/schema/snapshot.yaml`, the `sidereal_core`
models, and the frontend's `src/lib/schema.ts`.

| Collection | Holds | Tokens |
| --- | --- | --- |
| `students` | People being tutored | `status`: active, paused, archived |
| `sessions` | Tutoring sessions | `status`: scheduled, completed, cancelled |
| `documents` | Ingested source material, reduced to plain text; with no student it is the shared agency library | `kind`: transcript, web_page, question_bank, upload · `status`: pending, processing, ready, failed |
| `papers` | Exam papers from any source, normalised into one canonical structure that Typst templates render | `status`: draft, reviewed, archived |
| `questions` | Individual questions, extracted or written; shared like documents when no student is behind them | — |
| `topics` | A free tree of topics the tutor builds | — |
| `homework` | Homework assigned to a student | `status`: draft, assigned, submitted, marked · `format`: markdown, typst |
| `feedback` | Written feedback for a student | `status`: draft, sent |
| `plans` | Teaching plans covering a period | `status`: draft, active, completed |
| `generation_jobs` | LLM generation runs and their outcome | `kind`: homework, feedback, plan, paper_extract · `status`: queued, running, succeeded, failed |
| `homework_questions` | Junction, `homework` ↔ `questions` | — |
| `document_topics` | Junction, `documents` ↔ `topics` | — |
| `question_topics` | Junction, `questions` ↔ `topics` | — |
| `homework_topics` | Junction, `homework` ↔ `topics` | — |

`papers.structure` and `papers.mark_scheme` hold the canonical `Paper` and `MarkScheme` the
typeset service defines in `services/typeset/src/document.rs`; the structure is the source of
truth and a template renders it. A `papers` row with no `document` behind it, or one whose
document has no student, is the shared agency library exactly as `documents` is.

`tutoring`, `library` and `artefacts` are collection groups — folders in the admin app with no
table behind them — so a tutor sees students, material and generated work as three areas.

## Layering

```
                       sidereal-app ── frontend/   sidereal-mcp
                                   └──────┬───────────┘
                                   sidereal-generate
                                          │
                                   sidereal-ingest
                                          │
                                    sidereal-core
```

```
   services/transcripts  ──→  crates/sidereal-directus  ──→  crates/sidereal-common
```

- One-way: a lower layer never imports a higher one, and `sidereal-app` and `sidereal-mcp` are
  siblings that never import each other. Per-package `ruff.toml` banned-api entries enforce it.
- `sidereal-core` owns the Directus client and the domain models; `sidereal-ingest` is the only
  package that fetches; `sidereal-generate` is the only one that calls an LLM.
- `crates/` are libraries and are never deployed; `services/` are processes and are. A service
  binds `SIDEREAL_<SERVICE>_ADDR` and holds one port.
