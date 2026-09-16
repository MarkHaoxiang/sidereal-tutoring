// The question helpers the renderer calls. `paper.typ` and `worksheet.typ` are each
// concatenated after this file, so both kinds lay questions out identically.

#let marks-column = 3.2em
#let label-column = 1.9em
#let part-indent = 1.9em

#let marks-box(marks) = if marks == none { [] } else {
  text(size: 10pt, "[" + str(marks) + "]")
}

#let question-row(indent, label, marks, body, above: 0.9em, below: 0.5em) = block(
  width: 100%,
  above: above,
  below: below,
  sticky: true,
  grid(
    columns: (1fr, marks-column),
    column-gutter: 0.6em,
    align: (left + top, right + top),
    pad(
      left: indent,
      grid(
        columns: (label-column, 1fr),
        column-gutter: 0.3em,
        align: (left + top, left + top),
        label,
        body,
      ),
    ),
    marks-box(marks),
  ),
)

#let paper-question(number, marks, body) = question-row(
  0em,
  strong(number + "."),
  marks,
  body,
  above: 1.5em,
)

#let part(label, marks, body) = question-row(part-indent, "(" + label + ")", marks, body)

#let subpart(label, marks, body) = question-row(
  part-indent * 2,
  "(" + label + ")",
  marks,
  body,
)

#let answerlines(n, indent: 0em) = block(
  width: 100%,
  above: 1.4em,
  below: 1.1em,
  pad(
    left: indent,
    right: marks-column + 0.6em,
    stack(
      spacing: 1.6em,
      ..range(n).map(_ => line(length: 100%, stroke: 0.4pt + luma(65%))),
    ),
  ),
)
