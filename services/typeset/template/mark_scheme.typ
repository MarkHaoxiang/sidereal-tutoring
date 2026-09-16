// The house mark-scheme layout: one block per question, one ruled row per part.

#let scheme-note(body) = block(
  above: 0.65em,
  below: 0.1em,
  text(size: 9.5pt, style: "italic", fill: luma(38%), body),
)

#let scheme-row(label, marks, body) = block(
  width: 100%,
  above: 0em,
  below: 0em,
  grid(
    columns: (1.9em, 1fr, 3.2em),
    column-gutter: 0.5em,
    align: (left + top, left + top, right + top),
    inset: (y: 0.55em),
    stroke: (top: 0.4pt + luma(80%)),
    if label == none { [] } else { "(" + label + ")" },
    body,
    if marks == none { [] } else { text(size: 10pt, str(marks)) },
  ),
)

#let scheme-question(number, body) = block(
  width: 100%,
  above: 1.4em,
  below: 0.8em,
  {
    block(below: 0.5em, strong("Question " + number))
    body
    line(length: 100%, stroke: 0.4pt + luma(80%))
  },
)

#let mark-scheme(title: "", body) = {
  set document(title: title)
  set page(
    paper: "a4",
    margin: (x: 2.2cm, top: 2.2cm, bottom: 2.4cm),
    numbering: "1 / 1",
  )
  set text(font: "New Computer Modern", size: 11pt, lang: "en")
  set par(justify: false, leading: 0.7em, spacing: 1.15em)
  show math.equation: set text(font: "New Computer Modern Math")

  block(width: 100%, below: 1.2em, {
    text(size: 16pt, weight: "bold", title)
    v(0.3em)
    text(size: 10pt, tracking: 0.08em, fill: luma(35%), upper("Mark scheme"))
    v(0.45em)
    line(length: 100%, stroke: 0.7pt)
  })

  body
}
