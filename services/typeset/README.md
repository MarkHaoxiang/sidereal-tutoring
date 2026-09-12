# sidereal-typeset

Compiles Typst to PDF or SVG. The compiler is linked in, the fonts are in the binary, and the
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
```

`line` and `column` are 1-based positions in the submitted source; both are `null` for a
diagnostic that points at no source. A source the compiler rejects is always a 422 — never a
500. `#import "@preview/…"` and anything that reads a file (`read`, `include`, `image`) are
refused the same way, with a diagnostic saying why.

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
