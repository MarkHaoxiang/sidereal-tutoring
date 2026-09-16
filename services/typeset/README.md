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
                 "output": "pdf" | "svg" | "source"}      output defaults to pdf
     200  application/pdf bytes, {"pages": […]}, or {"source": "…"}
     400  {"message": …}   the body is not JSON
     413  {"message": …}   the rendered source is over 256 KiB
     422  {"errors": [{"path": "questions[2].parts[0].marks", "message": …}, …]}
     422  {"diagnostics": […]}   the rendered source did not compile
```

`line` and `column` are 1-based positions in the submitted source; both are `null` for a
diagnostic that points at no source. A source the compiler rejects is always a 422 — never a
500. `#import "@preview/…"` and anything that reads a file (`read`, `include`, `image`) are
refused the same way, with a diagnostic saying why.

## Rendering a document

`POST /render` takes the structure, not Typst: the renderer walks it and emits calls to the
helpers in `template/`, so every document of a kind comes out in the same house style.

```
Paper       { title, source?, board?, year?, time_minutes?, total_marks?, instructions?,
              questions: [Question] }
Question    { number: "1", stem?, marks?, answer_lines?, parts: [Part] }
Part        { label: "a", text, marks?, answer_lines?, parts: [Part] }
MarkScheme  { title, questions: [{ number, answer?, notes?,
                                   parts: [{ label, answer, marks?, notes? }] }] }
Worksheet   { title, student?, due?, intro?, questions: [Question] }
Markup      { text }
```

`worksheet` is the structured successor to the `homework` body of `POST /template`; both the
endpoint and `template/homework.typ` stay as they are. `Part.parts` nests one level only —
`(a)` then `(i)` — and `answer_lines` is capped at 60. Every other field is optional, and a
field the structure does not have is a 422 naming its path rather than a silently dropped
value.

`title`, `source`, `board`, `student`, `due`, `number` and `label` are plain text. `stem`,
`text`, `instructions`, `intro`, `answer` and `notes` carry Typst markup — `$x^2$`, `*bold*`,
`_emph_`, lists — but not Typst code: `\`, `#`, `[` and `]` are escaped before the text is
placed in a helper's content block, and `/` is escaped where it would open a comment. So a
stray `]` in a question prints as `]` and cannot close the block, and a field can never call a
function. Markup that is merely wrong — an unclosed `$` — reaches the compiler and comes back
as a 422 with diagnostics whose line and column point into the rendered source, which
`"output": "source"` returns.

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
        { "label": "a", "text": "Find $(d y) / (d x)$.", "marks": 2, "answer_lines": 3 },
        { "label": "b", "text": "Hence find the stationary points of $C$.", "marks": 5,
          "answer_lines": 6 }
      ]
    }]
  }
}'
```

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
