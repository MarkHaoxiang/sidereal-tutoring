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
- **The house template is data, not code**: `template/homework.typ`, included with
  `include_str!` and returned verbatim by `/template`, so a wrapped source compiles on its own.
  Its `#question` and `#answerlines` helpers are the body-side contract the LLM prompt mirrors —
  renaming one means changing `README.md` and the generator prompt together.
