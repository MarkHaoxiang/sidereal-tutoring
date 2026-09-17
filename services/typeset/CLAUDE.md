# sidereal-typeset — invariants

## Invariants

- **The compiler's world has no filesystem, no packages and no network.** `Files` answers
  every file id the document asks for with an error, except a name that is one of the
  request's own assets; `typst-as-lib` is built without its `packages` feature, so no resolver
  that could fetch one exists. Nothing is ever read from or written to a disk.
- **Assets are in memory, for one request, keyed by name.** A name is not a path: it carries
  no `/`, is refused unless it ends in `.png`, `.jpg`, `.jpeg` or `.svg`, and the resolver
  matches on the name alone. They are decoded before the document is validated, so a `figure`
  naming an asset that was not sent is a 422 at its path and never reaches the compiler.
  One asset is at most 2 MiB and a request's assets at most 8 MiB, decoded; over either is a
  413. With no assets, `Files` denies everything, as it always did.
- **`@preview` and other package imports are rejected before compilation**, so a crafted
  document cannot intern file ids for packages that will never resolve.
- **A source the compiler rejects is a 422 carrying diagnostics, never a 500.** Line and column
  are resolved against the submitted source and are 1-based.
- **Fonts come only from `typst-assets`.** Nothing scans the host, so output does not depend on
  what is installed; `FONTCONFIG_FILE=/dev/null` must change nothing.
- **The typst crates are pinned to an exact version** in the workspace `Cargo.toml`; they are
  released in lockstep and `typst-as-lib` tracks one minor of them.
- **`/compile` runs on a blocking task with a 10 s timeout and a 256 KiB source limit.** The
  timeout cannot cancel the compiler; Typst's own iteration cap is what bounds the task.
- **It reaches no other service.** No Directus, so no `SIDEREAL_DIRECTUS_*`.
- **Binds `SIDEREAL_TYPESET_ADDR` (default `127.0.0.1:50052`) and nothing else** — one port.
- **The house templates are data, not code**: every file in `template/` is `include_str!`d and
  emitted verbatim, so a wrapped or rendered source compiles on its own.
- **`template/homework.typ` and `/template` are frozen.** `#question` and `#answerlines` are
  the body-side contract the LLM prompt mirrors — renaming one means changing `README.md` and
  the generator prompt together. `worksheet` is the structured successor, not a replacement.
- **The structure is the source of truth for `/render`.** A caller sends the document, never
  Typst; layout lives in `template/`, and turning structure into markup lives in `render.rs`
  and nowhere else. The helpers a rendered source may call are `paper-question`, `part`,
  `subpart`, `answerlines`, `answer-box`, `answer-choices`, `answer-essay`, `answer-grid`,
  `answer-table`, `section-heading`, `passage-block`, `passage-ref`, `code-block`,
  `data-table`, `figure-block`, `scheme-question`, `scheme-row` and `scheme-note`; adding a
  helper means adding it to the `.typ` file, not to the Rust.
- **`questions.typ` defines the question helpers once** and is concatenated before `paper.typ`,
  `worksheet.typ` and `fragment.typ`, so every kind lays questions out identically.
  `blocks.typ` does the same for the content blocks and goes before `mark_scheme.typ` too, so a
  marking table is set like every other table.
- **No template parameter is named `text`**: the layouts call `text()`, and a parameter of that
  name shadows it.
- **A heading is set, not flowed.** Every title — paper, worksheet, mark scheme, section,
  passage, `Question n` — sets `hyphenate: false` and is unjustified, so a paper's name never
  breaks mid-word ("Non-Calcu-lator") and a wrapped heading never stretches. The paper title
  also has a measure narrower than the text column, so a long one breaks at a space rather
  than at the hyphen in a name. Body text keeps the document's own justification and
  hyphenation.
- **A fragment is the paper, cropped.** `question` and `markup` call the same helpers through
  `fragment.typ`, whose page is the A4 text width (`210mm - 4.4cm`) and `height: auto`, so an
  svg fragment is always one page. Its margin is the overhang Typst's cap-height-to-baseline
  line box leaves outside the page, not padding — widening it would stop matching the paper.
- **`mark_scheme` is a sibling of `document`, not a field of it**, and belongs to
  `kind: "question"` alone; sent with any other kind it is a 422 at `mark_scheme`.
- **Deserialization is `deny_unknown_fields` everywhere**: a field the structure does not have
  is a 422 naming its path, never a dropped value. Field names are snake_case and stable —
  they are mirrored by the pydantic and TypeScript models.
- **The structure only ever grows.** A field is added with a default that renders what the
  document rendered before it existed, so every document already stored still comes out the
  same; `answer_lines` stays as the deprecated spelling of `{"type": "lines"}` and emits the
  identical call. Sending both spellings for one node is a 422, never a silent precedence.
- **A section's marks are the section's.** `choose` makes the answerable total `choose` times
  one question's marks, and only where they are all equal; `Paper.total_marks` is printed as it
  was sent and nothing computes a total that would contradict it.
- **A text field is markup, never code.** `\`, `#`, `[` and `]` are escaped before the text
  enters a helper's `[ ]` block, so the emitted block is always balanced and nothing in a
  field executes. No input reaches the compiler unbalanced; markup that is merely wrong is a
  422 with diagnostics, never a panic.
- **Prose outside `$…$` never fails to compile.** `<`, `>`, `@` and a backtick are escaped
  because a label, a reference and raw text are what the compiler would otherwise read; `/` is
  escaped where it opens a comment, ends one after `*`, or starts a term list at the head of a
  line; and `*` and `_` are paired as the compiler pairs them — per block, outside maths,
  ignoring one inside a word — with every unclosed or crossed delimiter escaped. Adding a
  character to that set means adding a case to `escape` and a compiled test, never a guess:
  `services/typeset/src/render.rs` decides this and nothing else does.
- **Inside `$…$` nothing is escaped beyond the four structural characters**, because there
  `<`, `@` and `*` are operators. The maths tracker works by toggling on `$`, which is sound
  only because no `$` is ever added or removed.
- **A markup field keeps its lines**: the break is emitted after the escaping, so it is the
  renderer's `\` and never the field's own.
- **A table's header and cells are markup**, escaped and set exactly as a stem is, so an
  exponent a document sends as `$10^3$` is typeset and not flattened.
- **A `passage` and a `code` block are strings, not markup**: they are emitted as Typst string
  literals and set line for line, so nothing in them is parsed and nothing in them executes.
- **Every extent is capped**: `Part.parts` nests one level, `answer_lines` and `answer.lines`
  at 60, `height_mm` at 250, options at 26, a grid at 40 × 26, a table at 40 × 12, a figure at
  165 mm — all validation errors in the same `{"errors": [{"path", "message"}]}` shape as a
  serde failure, so nothing can be asked for that will not fit on A4.
