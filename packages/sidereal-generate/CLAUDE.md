# sidereal-generate

Sits above sidereal-ingest. Imports core and ingest only.

## Invariants

- Every generator is one `Generator[OutputT]` implementation, so two can be compared on the same request.
- `SIDEREAL_GENERATE_BACKEND` decides what `default_generators()` builds: `claude` (default),
  `openrouter` or `fake`. Fake output is prefixed `[fake]` and says so in its body; it never passes as
  real generation.
- No network at import and none in tests. The SDK client is built on first `generate()`, never in
  `__init__`, so constructing a generator needs no credentials.
- Both backends send the same `strict_schema` of the same output model, so two can be compared on the
  same request. The model id is configuration (`SIDEREAL_GENERATE_MODEL`, `OPENROUTER_MODEL`), never a
  commit, and `admin_health` reports the one the chosen backend calls.
- Claude asks through a forced strict tool call whose `input_schema` is that schema. Every output
  field is required and optional ones are nullable — a strict schema has no optional properties.
- OpenRouter asks for `response_format` `json_schema` with `strict: true` first; a 400 or 404 means the
  model has no strict mode, and the same schema goes out once as a forced function call. That refusal
  is remembered for the life of the generator.
- A missing `OPENROUTER_API_KEY` is a `GenerationNotConfiguredError` raised before any request, and the
  job says so in a sentence.
- The model's reasoning is spent from `max_tokens`, so a budget sized to the answer alone can be gone
  before the answer starts. `finish_reason: length` is a `GenerationTruncatedError` and its own
  sentence — never "returned nothing" — and an extraction carries the larger
  `SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS` budget. The `claude` backend clamps that to the 21,333
  above which its SDK demands streaming, which nothing here does yet.
- Every model call leaves one INFO line carrying `finish_reason` and `usage`: a paid call says what it
  cost without anyone raising the log level.
- A reply with no tool call, or one that fails validation, raises `GenerationError`. A half-filled
  artefact is never returned.
- Prompts are module-level constants in `prompts.py`, not built at call time.
- Generators return pydantic outputs only. `jobs.py` is the one place a generated artefact is written
  back to Directus, and the one place that knows the provenance shape (`job`, `model`, `documents`).
- `run_job` never raises for a generation failure: the job row carries the outcome, so every failure is
  visible to the tutor and to an agent.
- A job's `error` is one plain sentence a tutor can act on. The exception behind it is logged at error
  level, never stored.
- A homework job writes the generated questions as `questions` rows, links each to the homework with a
  `homework_questions` row sorted from 1 in the order generated, and records their ids in
  `generated_from`.
- `JobInput.format` is homework's alone; `typst` on any other kind is refused at the app and the MCP
  surface, before a job row exists.
- A Typst job asks for a *body* — the house helpers and Typst maths, no preamble — wraps it through
  the service's `/template`, and compiles it. `content` is always the wrapped source, so
  `recompile_homework` can compile the row again.
- A body that will not compile is generated once more with the compiler's report appended to
  `instructions`. If it still fails the row is written anyway: `compile_error` set, `pdf` null, a
  `warning` in `generated_from`, and the job succeeds. A generated artefact is never discarded.
- `recompile_homework` keeps the PDF that is already on the row when the new source fails, so a tutor
  never loses a working handout to a bad edit.
- A paper's `structure` is the source of truth. Its PDFs are renderings of it and can be made again;
  nothing is read back out of a PDF.
- A paper's `questions` rows are derived from the same structure: an extract writes them, and they
  are never merged into by hand. Re-extracting a document writes a new paper with its own rows.
- Extraction is transcription, not generation: one strict tool call whose schema is
  `PaperExtraction`. A payload the canonical models refuse is asked for once more with the errors
  appended; a second refusal is a `GenerationError` and no paper is written.
- A render that fails leaves the row, a `generated_from.warning` and a succeeded job — the structure
  is the work. A `rerender_paper` failure is the tutor's to see, so it raises.
- `paper_extract` carries one document and no student, or two with the mark scheme second; every
  other kind carries a student. Either mismatch is a `JobInputError` whose sentence the tutor reads.
- Maths is normalised before any compile and after every repair: inside `$...$`, a name Typst does
  not know becomes quoted text and `dx` becomes `dif x`. The compiler stops at the first unknown
  variable, so a fault left in costs a whole round-trip to the model to find.
- Source the compiler still refuses is sent back with its diagnostics for a repair that may change
  only the maths, at most twice, at extraction and at every later render. What compiled is written
  back to the row, so a tutor's next render starts from source the renderer accepts.
- A job files what its calls cost in `generated_from.usage`, summed over the extraction, its retry
  and every repair. A price is filed only when every call in the job carried one.
- Transcription asks for little thinking: an extraction and a repair send
  `SIDEREAL_GENERATE_REASONING` (`low` by default) and file the effort they used, because reasoning
  is spent from the same budget as the answer. Writing homework, feedback or a plan sends no effort
  and leaves the depth to the model.
- `strict_schema` is what makes every property required: the canonical models carry defaults so a
  hand-edited structure still reads, and a strict schema has no optional properties.
