# sidereal-typeset — invariants

## Invariants

- **The compiler's world has no files, no packages and no network.** `NoFiles` answers every
  file id the document asks for with an error, and `typst-as-lib` is built without its
  `packages` feature, so no resolver that could fetch one exists. Adding a file resolver would
  break this.
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
  `subpart`, `answerlines`, `scheme-question`, `scheme-row` and `scheme-note`; adding a helper
  means adding it to the `.typ` file, not to the Rust.
- **`questions.typ` defines the question helpers once** and is concatenated before `paper.typ`,
  `worksheet.typ` and `fragment.typ`, so every kind lays questions out identically.
- **A fragment is the paper, cropped.** `question` and `markup` call the same helpers through
  `fragment.typ`, whose page is the A4 text width (`210mm - 4.4cm`) and `height: auto`, so an
  svg fragment is always one page. Its margin is the overhang Typst's cap-height-to-baseline
  line box leaves outside the page, not padding — widening it would stop matching the paper.
- **`mark_scheme` is a sibling of `document`, not a field of it**, and belongs to
  `kind: "question"` alone; sent with any other kind it is a 422 at `mark_scheme`.
- **Deserialization is `deny_unknown_fields` everywhere**: a field the structure does not have
  is a 422 naming its path, never a dropped value. Field names are snake_case and stable —
  they are mirrored by the pydantic and TypeScript models.
- **A text field is markup, never code.** `\`, `#`, `[` and `]` are escaped before the text
  enters a helper's `[ ]` block, and `/` is escaped where it would open a comment, so the
  emitted block is always balanced and nothing in a field executes. No input reaches the
  compiler unbalanced; markup that is merely wrong is a 422 with diagnostics, never a panic.
- **`Part.parts` nests one level and `answer_lines` is capped**; both are validation errors in
  the same `{"errors": [{"path", "message"}]}` shape as a serde failure.
