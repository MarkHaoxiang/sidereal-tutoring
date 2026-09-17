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
- A cut-off answer is asked for once more with twice the budget, and a second cut-off is the
  tutor's failure: `finish_reason: length` on OpenRouter and `stop_reason: max_tokens` on Claude
  are the same `GenerationTruncatedError` either way. A plan starts from
  `SIDEREAL_GENERATE_PLAN_MAX_TOKENS`, above every other kind, because it covers a whole period in
  one answer; the `claude` backend clamps both the start and the doubling to
  `NON_STREAMING_MAX_TOKENS`.
- A reply with no tool call, or one that fails validation, raises `GenerationError`. A half-filled
  artefact is never returned.
- Prompts are module-level constants in `prompts.py`, not built at call time.
- Every kind is given today's date and the date of the student's next scheduled lesson, and every
  date in a prompt is printed with its weekday beside it: a model left to work one out names the
  wrong day, and the weekday names are a constant here rather than the locale's `strftime`.
- A feedback job is given the hand-ins it is about: each homework's questions as text, the
  student's typed answers, the transcription of their photographed working and the tutor's marks.
  A hand-in with nothing on it says so in words rather than going quiet — silence is what let
  feedback praise working it had never seen. The row is filed against the first of them
  (`feedback.homework`), and `generated_from.homework` carries them all.
- `retry_job` starts a new job from a failed one's own input. The row that failed is never
  rewritten: it is the history.
- Generators return pydantic outputs only. `jobs.py` is the one place a generated artefact is written
  back to Directus, and the one place that knows the provenance shape (`job`, `model`, `documents`).
- `run_job` never raises for a generation failure: the job row carries the outcome, so every failure is
  visible to the tutor and to an agent.
- A job's `error` is one plain sentence a tutor can act on, and the exception behind it is logged
  at error level, never stored — except a `GenerationError`, whose own sentence is carried too,
  clipped to `ERROR_DETAIL`: "the generated result could not be used" alone told an admin nothing
  about which question an extraction could not read.
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
- A paper's `questions` rows are derived from the same structure: an extract writes them and a
  scheme re-run refreshes their `mark_scheme` in place, and they are never merged into by hand.
  Re-extracting a document writes a new paper with its own rows.
- Extraction is transcription, not generation, and it is chunked: a shape call, then the
  questions in runs of `BATCH_QUESTIONS`, then a block call for the questions the shape flagged,
  then the mark scheme in the same runs. One schema over a whole paper is a grammar the provider
  refuses to compile.
- Every schema an extraction or a repair sends stays at or under 4,101 bytes and 8 `$defs` — the
  largest the provider was proved to compile, against 6,521 it refused. Tests assert it per
  schema and over every call one extraction makes.
- The block union the model authors is `passage`, `passage_ref`, `code` and `table`: a `figure`
  is the app's to crop and place, and the union without it is part of what makes the schemas fit.
- `chunks.py` is pure — the splitting, the page selection and the merge — and
  `ChunkedPaperExtractor` sits on one `BatchCaller.ask`, so the whole flow is driven in tests
  with no network. A backend supplies the caller and nothing else.
- The shape is the paper's order of record: its question order, its sections and its passages are
  what the merge rebuilds. A batch answer the shape did not ask for is logged and dropped.
- A batch question the shape has not, whose unmatched stubs are that number plus a separated
  suffix — `01` against `01.1`, `01.2` — takes their place and their section, and they are
  retired. A stub is never renumbered without a transcription keyed to it: `10` is no part of `1`.
- Reconciliation runs before the block call, so it asks under the numbering the transcription
  settled on.
- A skeleton summary is never stored as a paper's wording: a question left untranscribed after
  reconciliation is a `GenerationError` naming it, not a one-line stem.
- A question or part a batch asked a figure for and gave no wording is asked once more, once per
  batch; a second wordless answer is a `GenerationError`. A figure never carries a question's
  only text.
- A stemless question's lone unlabelled part is its stem: its text, answer and blocks come up with
  it and its own parts become the question's. A labelled part, or a second one, is left alone, and
  a question that got its stem this way is not wordless.
- A mark-scheme run is checked against the numbers and the part labels it was asked for, and asked
  once more naming the ones it answered nothing under; only those gaps are taken from the second
  answer.
- A scheme entry answers every label its question prints: a part with sub-parts under each `a(i)`,
  or under `a` where the scheme marks it as a whole; a question with parts under each of its own
  labels, or under a non-blank whole `answer` where the entry carries no parts; a question with no
  parts by an `answer` of its own.
- A scheme still missing entries or labels is a `GenerationError` naming them, and one that answered
  none of the paper says that instead. A scheme covering part of a paper is never stored.
- A sectioned paper's top-level `questions` stays empty. That is the paper's shape, not a loss.
- The merged result is validated as a whole `CanonicalPaper`; one that will not validate is a
  `GenerationError` and no half paper is written.
- A call whose answer does not fit is asked once more with the validator's errors, and those
  errors go in a WARNING; a second failure is a `GenerationError` whose sentence names what could
  not be read.
- A repair goes out in the same runs against the same batch schema. Only wording comes back from
  it: marks, answers, blocks, sections and passages are kept from what was already read.
- An object field that arrives as a JSON string is parsed once and the model named in a WARNING.
  Text that opens as JSON and will not parse says so at WARNING and has its invalid escapes
  doubled once — `\p` is the backslash a maths field meant — and if it still will not parse it is
  left for validation to refuse. A string that is not JSON is untouched. A forced tool call is not
  grammar-constrained, so a stringified field is a real answer, never text to store.
- Every model call logs the raw answer it was given at DEBUG, cut to `DEBUG_PREFIX` bytes.
- A paper is read from its text unless its pages go up as images too: `pages=True` sends them,
  `False` never does, and the default asks the PDF — images on a fifth of its pages or more. A
  retry carries the same pages, and an extraction that sends pages says at INFO how many went and
  how many of them are drawn.
- The shape call is the one that sees every page image, because it is what says which page each
  question starts on. Each later run sees only the pages its questions span, through to where the
  next run starts, which is what makes a batch cheaper than the whole paper.
- The pages a run is shown are named to it by the paper's own number, never by their position in
  the batch, so a figure request locates itself in the source PDF. The drawn ones among them come
  from `raster_pages` and never from the model's judgement.
- `QuestionBatch.figures` carries no default: an omitted key is a `ValidationError` down the
  retry path, never an empty list a run with figures reads the same as.
- `pages=True` on a document with no PDF behind it is a `PaperError` the tutor reads; a PDF that
  will not rasterise fails the same way, and falls back to the text when nobody asked for pages.
- Only `SIDEREAL_GENERATE_BACKEND=openrouter` can see a page image. Every other backend answers
  one sentence naming it — a text-only extraction a tutor believes read the figures is worse.
- The figure requests a run returns are the model's side list, gathered into
  `PaperExtraction.figures`, never structure and never stored: each request is cropped out of the
  source PDF, filed, and appended as a `figure` block to the question or part it names, searching
  the sections as well as the top level. A request naming a
  node the paper has not got, and a crop that fails, are logged and dropped — the paper is the
  work.
- A figure's asset name is `<file id>.jpg`: the service refuses a name that is not a file name,
  and the render step strips the suffix to fetch the bytes.
- A `figure` block's `width_mm` is the width ingest measured on the source page, so a small
  diagram does not print the width of the column. Whether the crop was snapped to the drawn
  objects is logged and never stored: the canonical models carry no provenance.
- Every render sends its figures' bytes beside the structure, inside the service's per-asset and
  total limits. A `figure` block whose bytes are not being sent is stripped from the copy that
  goes to render and kept in the stored structure, so a later render with room still prints it.
- A JSON escape a model wrote into a text field is decoded where its answer is read: `12\u00b0`
  is six characters the renderer would print, and `unescaped` turns every one back into its
  character before validation.
- A signed script is grouped before any compile: `10^-2` raises the sign alone, so `normalise`
  writes `10^(-2)`.
- A `passage` block that only restates its own question's wording is dropped — at the merge, so
  it is never stored, and again where a worksheet is cut, so a paper read before that still
  prints its choice questions once.
- A figure crop is uploaded into the shared figures folder. A crop a tutor cannot read is left
  out of the render and its `figure` block with it, which is a sheet with no diagrams and no
  error.
- A feedback job is given the sheet as the student received it beside the questions it was
  generated from, and is told to state the total the tutor gave: after an edit the two differ,
  and the sheet is what was answered.
- A retry whose student has been deleted is a `JobStudentGoneError` before any write;
  `paper_extract` carries no student and retries either way.
- A worksheet's PDF is rendered, not compiled from its source: `/compile` carries no assets, so
  an `image()` in the source resolves to nothing.
- A worksheet carries each chosen question's own blocks, and a `passage_ref` is printed inline from
  the paper's `passages`: a worksheet has none of its own, so a reference left as one renders as
  nothing. A reference the paper cannot resolve is dropped and logged.
- A worksheet made for a student also becomes a draft homework — `typst`, the rendered source as
  `content`, the filed PDF, the due date, and `homework_questions` to the paper's own question rows
  in the order chosen — and `WorksheetResult.homework_id` is how the caller finds it. A number the
  paper has no row for is logged, never raised. Such a row is re-rendered rather than recompiled:
  its `content` names figure assets `/compile` cannot carry.
- `questions` rows are written for every question the paper asks, a section's as well as a
  top-level one, and a worksheet may take either.
- A render that fails leaves the row, a `generated_from.warning` and a succeeded job — the structure
  is the work. A `rerender_paper` failure is the tutor's to see, so it raises.
- A mark scheme that cannot be completed does the same: the paper is stored with `mark_scheme` null,
  a `generated_from.warning` and a succeeded job, never lost with the scheme.
- `extract_paper_mark_scheme` reads the scheme alone against a stored paper's structure, files the
  document it read under `generated_from`, and clears that warning when it succeeds. It then
  PATCHes each `questions` row's `mark_scheme` by number: a row or an entry the other has not is
  logged, never raised, and no row is deleted or rewritten whole.
- `paper_extract` carries one document and no student, or two with the mark scheme second; every
  other kind carries a student. Either mismatch is a `JobInputError` whose sentence the tutor reads.
- Maths is normalised before any compile and after every repair: inside `$...$`, a name Typst does
  not know becomes quoted text, `dx` becomes `dif x`, and a span opening on `^` or `_` — `kg$^-1$`
  — is given the empty base it has no operand without. The compiler stops at the first unknown
  variable, so a fault left in costs a whole round-trip to the model to find. A `passage` and a
  `code` block are verbatim, so their `text` is never normalised.
- Source the compiler still refuses is sent back with its diagnostics for a repair that may change
  only the maths, at most twice, at extraction and at every later render. A repair addresses the
  document that failed alone, so a fault in the mark scheme never costs a paper round. What
  compiled is written back to the row, so a tutor's next render starts from source the renderer
  accepts.
- A job files what its calls cost in `generated_from.usage`, summed over every call it made — the
  shape, every run, the blocks, the mark scheme, each retry and each repair. A price is filed only
  when every call in the job carried one.
- `usage` stays the extraction's own cost. A re-run appends one `generated_from.reruns` entry — its
  kind, the document it read, its own usage, the model and an aware UTC timestamp — and never
  replaces an earlier one; `generated_from.usage_total` is the sum across the extraction and every
  re-run. A re-run whose backend recorded no call files `usage` null, never a zero.
- Transcription asks for little thinking: an extraction and a repair send
  `SIDEREAL_GENERATE_REASONING` (`low` by default) and file the effort they used, because reasoning
  is spent from the same budget as the answer. Writing homework, feedback or a plan sends no effort
  and leaves the depth to the model.
- Handwriting is read by `SIDEREAL_GENERATE_BACKEND=openrouter` alone: the pages go up as JPEG image
  parts on the same `OpenRouterCall`, one call for the whole scan, against `Transcription`'s strict
  schema, on the extraction budget and reasoning effort. Every other backend answers one sentence
  saying which one can.
- A transcriber's failures are `IngestError`s, because the protocol is ingest's: the tutor reads the
  sentence and the exception behind it is logged, never stored.
- `strict_schema` is what makes every property required: the canonical models carry defaults so a
  hand-edited structure still reads, and a strict schema has no optional properties.
