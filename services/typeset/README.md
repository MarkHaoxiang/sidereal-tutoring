# sidereal-typeset

Compiles Typst to PDF or SVG, and renders exam papers, mark schemes and worksheets from their
structure into the house style. The compiler is linked in, the fonts are in the binary, and the
world it compiles against has no files, no packages and no network.

```sh
cargo run -p sidereal-typeset
```

| Variable | Default | |
| --- | --- | --- |
| `SIDEREAL_TYPESET_ADDR` | `127.0.0.1:50052` | listen address |
| `RUST_LOG` | `info` | log filter |

SIGINT or SIGTERM stops the server.

```sh
cargo test -p sidereal-typeset
```

## Endpoints

```
GET  /healthz                                   200 "ok"
POST /compile   {"source": "…", "output": "pdf" | "svg"}     output defaults to pdf
     200  application/pdf bytes, or {"pages": ["<svg…>", …]}
     413  {"message": …}   source over 256 KiB
     408  {"message": …}   compilation over 10 s
     422  {"diagnostics": [{"message", "line", "column", "severity"}, …]}
POST /template  {"kind": "homework", "title": "…", "student": "…"|null,
                 "due": "2026-09-25"|null, "body": "…"}
     200  {"source": "…"}  the body wrapped in the house template
POST /render    {"kind": "paper" | "mark_scheme" | "worksheet" | "question" | "markup",
                 "document": {…}, "mark_scheme": {…}|null,
                 "assets": {"figure-1.png": "<base64>", …},
                 "output": "pdf" | "svg" | "source"}      output defaults to pdf
     200  application/pdf bytes, {"pages": […]}, or {"source": "…"}
     400  {"message": …}   the body is not JSON
     413  {"message": …}   the rendered source is over 256 KiB, one asset over 2 MiB,
                           or the assets over 8 MiB together
     422  {"errors": [{"path": "questions[2].parts[0].marks", "message": …}, …]}
     422  {"diagnostics": […]}   the rendered source did not compile
```

`line` and `column` are 1-based positions in the submitted source; both are `null` for a
diagnostic that points at no source. A source the compiler rejects is always a 422 — never a
500. `#import "@preview/…"` and anything that reads a file (`read`, `include`, `image`) are
refused the same way, with a diagnostic saying why — except an `image` of one of the request's
own assets, which is how a figure is drawn.

## Rendering a document

`POST /render` takes the structure, not Typst: the renderer walks it and emits calls to the
helpers in `template/`, so every document of a kind comes out in the same house style.

```
Paper       { title, source?, board?, year?, time_minutes?, total_marks?, instructions?,
              questions: [Question], sections: [Section], passages: [Passage] }
Section     { title?, instructions?, choose?: int, questions: [Question] }
Passage     { id, title?, text }
Question    { number: "1", stem?, marks?, blocks: [Block], answer?: Answer,
              answer_lines?: int, parts: [Part] }
Part        { label: "a", text, marks?, blocks: [Block], answer?: Answer,
              answer_lines?: int, parts: [Part] }
Answer      { type: "lines" | "box" | "multiple_choice" | "essay" | "grid" | "table" | "none",
              lines?: int, options?: [{ label?, text }],
              height_mm?: int, rows?: int, cols?: int }
Block       { type: "passage",      title?, text }
            { type: "passage_ref",  id }
            { type: "code",         language?, text }
            { type: "table",        caption?, header?: [string], rows: [[string]] }
            { type: "figure",       asset, caption?, width_mm?: int }
MarkScheme  { title, questions: [{ number, answer?, notes?, blocks: [Block],
                                   parts: [{ label, answer, marks?, notes?,
                                             blocks: [Block] }] }] }
Worksheet   { title, student?, due?, intro?, questions: [Question] }
Markup      { text }
```

`worksheet` is the structured successor to the `homework` body of `POST /template`; both the
endpoint and `template/homework.typ` stay as they are. `Part.parts` nests one level only —
`(a)` then `(i)`. Every field but the ones shown without a `?` is optional, an absent array is
an empty one, and a field the structure does not have is a 422 naming its path rather than a
silently dropped value.

`title`, `source`, `board`, `student`, `due`, `number`, `label`, `id`, `asset` and `language`
are plain text. `stem`, `text`, `instructions`, `intro`, `answer`, `notes`, an option's `text`
and a table's `caption`, `header` and cells carry Typst markup — `$x^2$`, `*bold*`, `_emph_`,
lists — but not Typst code, and not by accident.

**Prose is prose.** `\`, `#`, `[` and `]` are escaped, so a stray `]` prints as `]` and cannot
close the block and a field can never call a function. Outside a `$…$` span, so are the
characters ordinary prose walks into: `<` and `>` (a label — `a <3 b` is an unclosed label and
`<name>` silently becomes one), `@` (a reference — `email@example.com` names a label that does
not exist), a backtick (raw text), and `/` where it would open a comment, end one after a `*`,
or start a term list at the beginning of a line. `*` and `_` are paired the way the compiler
pairs them — per block, outside maths, and ignoring one inside a word like `snake_case` — and
any left open or crossed (`*a _b* c_`) is escaped. So `a < b`, `20% * VAT`, `sep_ate*` and
`/ no colon` all print, and none of them is a compile error.

The cost is that a line may open a list with `- `, `+ ` or `1. ` but not a term list with
`/ `, and a backtick never opens a raw span — `code` blocks are what listings are for.

Inside `$…$` nothing is touched, because there `<`, `@` and `*` are operators. Maths that is
merely wrong — an unclosed `$`, an unknown symbol — reaches the compiler and comes back as a
422 with diagnostics whose line and column point into the rendered source, which
`"output": "source"` returns.

A markup field keeps its own lines: **one newline is a line break and a blank line is a
paragraph break**, so a poem, a play extract or a numbered instruction prints as it was
written. The exception is a line that starts a list, a heading or a term (`- one`, `+ one`,
`1. one`, `= Heading`, `/ Term: …`) — Typst already sets those on a line of their own, so no
break is added before one. Text whose indentation matters belongs in a `passage` or `code`
block, which are set verbatim.

```sh
curl -sS localhost:50052/render -H 'content-type: application/json' -o paper.pdf -d '{
  "kind": "paper",
  "output": "pdf",
  "document": {
    "title": "Pure Mathematics 1", "board": "Edexcel", "year": 2025,
    "time_minutes": 90, "total_marks": 75,
    "instructions": "Answer *all* questions in the spaces provided.",
    "questions": [{
      "number": "1",
      "stem": "The curve $C$ has equation $y = x^3 - 6x^2 + 9x + 1$.",
      "parts": [
        { "label": "a", "text": "Find $(d y) / (d x)$.", "marks": 2,
          "answer": { "type": "lines", "lines": 3 } },
        { "label": "b", "text": "Hence find the stationary points of $C$.", "marks": 5,
          "answer": { "type": "lines", "lines": 6 } }
      ]
    }]
  }
}'
```

### Sections and choice

`Paper.sections` is a run of questions under one heading; where it is used `Paper.questions`
may be empty, and where both are used the loose questions are printed first. A section prints
its `title`, its own marks total, `Answer N of the following questions.` when `choose` is set,
and then its `instructions`.

The section's total is the **answerable** one: with `choose`, `choose` × one question's marks,
and only where every question in the section is worth the same — anything else has no single
answer and no total is printed. Without `choose` it is the sum. Either way the paper's own
`total_marks` is printed exactly as it was sent: nothing here adds a total that would
contradict it.

```json
{ "title": "Section A: Shakespeare",
  "instructions": "Answer *one* question in this section.",
  "choose": 1,
  "questions": [
    { "number": "01", "stem": "Explore the presentation of jealousy in *Othello*.", "marks": 25 },
    { "number": "02", "stem": "Explore the presentation of power in *Othello*.", "marks": 25 }
  ] }
```

### Answer types

`Question.answer` and `Part.answer` are the space the student writes in, printed after the
node's blocks and before its parts. `type` decides which of the other fields are read; the
rest are ignored.

| `type` | reads | prints |
| --- | --- | --- |
| `lines` | `lines` (default 4, at most 60) | ruled lines |
| `box` | `height_mm` (default 40, at most 250) | a bordered box |
| `multiple_choice` | `options` (1 to 26) | a lettered list, each option with a lozenge to shade |
| `essay` | `height_mm` (default 230, at most 250) | a ruled block as tall as it asks for |
| `grid` | `rows` (≤ 40), `cols` (≤ 26) | squared paper, 5 mm to a cell |
| `table` | `rows` (≤ 40), `cols` (≤ 12) | an empty table |
| `none` | — | nothing |

An option's `label` is the letter the paper printed; leave it out and the options are lettered
A, B, C… in order. The renderer adds no instruction of its own — "shade one lozenge", "circle
your answer" and the like belong in the stem, where the paper put them.

`answer_lines: n` is the deprecated spelling of `{"type": "lines", "lines": n}` and emits the
same call; sending both for one node is a 422 at `answer_lines`.

```json
{ "number": "07", "marks": 1,
  "stem": "Which quantity has the base unit $k g space m^2 space s^(-2)$?\nShade *one* lozenge.",
  "answer": { "type": "multiple_choice", "options": [
    { "text": "kinetic energy" }, { "text": "momentum" },
    { "text": "the Young modulus" }, { "label": "D", "text": "power" }
  ] } }
```

### Content blocks

`Question.blocks` and `Part.blocks` are the material set between the stem and the parts — and
a `MarkScheme` entry may carry the same blocks, which is where a marking table goes.

- **`passage`** — an extract, set verbatim in a tinted block with a rule down its left. Its
  `text` is a string, not markup: every line, blank line and leading space survives, and
  nothing in it is read as Typst.
- **`code`** — a listing, set in monospace with `language` highlighted if Typst knows it. Its
  `text` is verbatim too, so a `#` prints as `#`.
- **`table`** — a Typst table. `header` is one row of column names; every row must have as
  many cells as the header (or as the first row, when there is no header), or it is a 422 at
  `blocks[i].rows[j]`.
- **`figure`** — an image from the request's `assets`, centred, `width_mm` wide or as wide as
  the column.
- **`passage_ref`** — a pointer to a `Paper.passages` entry. The passages are printed once, in
  order, at the start of the paper, just after the instructions; the reference prints a line
  naming the one this question needs. An id that is in no passage is a 422 at `blocks[i].id`.

```json
{ "number": "2", "stem": "The program below sums a list.",
  "blocks": [
    { "type": "code", "language": "python",
      "text": "def total(values):\n    return sum(values)" },
    { "type": "table", "caption": "Table 1: the recorded times.",
      "header": ["Gate", "Time / $s$"], "rows": [["A", "0.00"], ["B", "0.41"]] },
    { "type": "figure", "asset": "figure-1.png", "caption": "Figure 1", "width_mm": 70 },
    { "type": "passage_ref", "id": "ozymandias" }
  ] }
```

### Assets

A `figure` block names a file, and `assets` is where the bytes come from: a map of that same
name to standard base64. Whitespace inside a value and a leading `data:image/png;base64,`
prefix are ignored.

```json
{ "kind": "paper", "document": { … },
  "assets": { "figure-1.png": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB…" } }
```

The name is a name, never a path: letters, digits, `.`, `-` and `_`, at most 128 characters,
ending in `.png`, `.jpg`, `.jpeg` or `.svg` — which is how the format is read. The bytes live
in memory for the length of the one request, are reachable only by that name, and are never
written anywhere. One asset may be 2 MiB and all of them 8 MiB together, decoded; over either
is a 413. A `figure` naming an asset that was not sent is a 422 at `blocks[i].asset` before
the compiler runs. `kind: "question"` takes `assets` too, so the app can show one question with
its figure.

## Rendering a fragment

`question` and `markup` render one node rather than a document, for showing a tutor one
question — or one field they are editing — as it will be printed. `question` takes a
`Question` as its `document` and may carry one `MarkScheme` question entry in a sibling
`mark_scheme`, drawn under it. `markup` takes `{"text": "…"}`, the same markup a text field
carries, escaped the same way.

A fragment has no header, no page numbering and no margins: it is set on a page as wide as an
A4 paper's text column and only as tall as the fragment, so `"output": "svg"` is always one
page and the crop is tight. Everything else is the paper's — same helpers, same fonts, same
line breaks.

```sh
curl -sS localhost:50052/render -H 'content-type: application/json' -d '{
  "kind": "question", "output": "svg",
  "document": {
    "number": "4",
    "stem": "The curve $C$ has equation $y = x^3 - 6x^2 + 9x + 1$.",
    "parts": [
      { "label": "a", "text": "Find $(d y) / (d x)$.", "marks": 2 },
      { "label": "b", "text": "Hence find the stationary points of $C$.", "marks": 5 }
    ]
  },
  "mark_scheme": {
    "number": "4",
    "parts": [{ "label": "a", "answer": "$(d y) / (d x) = 3x^2 - 12x + 9$", "marks": 2 }]
  }
}'
```

Typst bakes fill colours into its SVG — the page ships as a white rectangle behind black
glyphs — so a fragment must be shown on a paper-coloured surface, in a dark theme too, and
never tinted by inheriting the surrounding text colour.

## Writing a homework body

`POST /template` returns the house template followed by your body, as one source you can send
straight to `POST /compile`. The template sets A4, margins, page numbering and New Computer
Modern for text and maths, and draws the header from `title`, `student` and `due`. Your body
supplies the questions and may use anything in the Typst standard library plus two helpers:

- `#question[…]` — one numbered question. Numbering is automatic and restarts per document;
  the block leaves a small gap after itself.
- `#answerlines(n)` — `n` ruled lines of answer space.

```typ
#question[
  Factorise $x^2 - 5x + 6$.
]
#answerlines(3)

#question[
  Hence solve $x^2 - 5x + 6 = 0$, and sketch $y = x^2 - 5x + 6$.
]
#answerlines(6)
```

Maths is Typst maths: `$…$` inline, `$ … $` (with spaces inside the delimiters) as a display
block. `#pagebreak()` starts a new page.
