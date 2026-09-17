// The question helpers the renderer calls. `paper.typ` and `worksheet.typ` are each
// concatenated after this file, so both kinds lay questions out identically.

#let marks-column = 3.2em
#let label-column = 1.9em
#let part-indent = 1.9em

// One ruled line to the next. Absolute, so an answer space given in millimetres can be turned
// into a line count.
#let answer-line-step = 17.6pt
#let answer-rule = 0.4pt + luma(65%)

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
      spacing: answer-line-step,
      ..range(n).map(_ => line(length: 100%, stroke: answer-rule)),
    ),
  ),
)

// Every answer space but the ruled lines sits in the same column they do.
#let answer-space(body, indent: 0em) = block(
  width: 100%,
  above: 1.4em,
  below: 1.1em,
  breakable: false,
  pad(left: indent, right: marks-column + 0.6em, body),
)

#let answer-box(height, indent: 0em) = answer-space(
  indent: indent,
  box(
    width: 100%,
    height: height,
    stroke: 0.6pt + luma(55%),
    radius: 2pt,
  ),
)

// A ruled block as tall as it was asked for, so an essay gets a page and a short answer does
// not. The line count is the height the layout can actually fill.
#let answer-essay(height, indent: 0em) = answerlines(
  calc.max(1, int(height / answer-line-step)),
  indent: indent,
)

// The shape a student shades or circles. One per option, with the paper's own letter when it
// printed one and A, B, C… when it did not.
#let choice-mark = box(
  width: 1.25em,
  height: 0.66em,
  radius: 0.33em,
  stroke: 0.7pt + luma(35%),
  baseline: 0.02em,
)

#let answer-choices(options, indent: 0em) = answer-space(
  indent: indent,
  {
    set par(justify: false)
    stack(
      spacing: 0.8em,
      ..options
        .enumerate()
        .map(((index, option)) => grid(
          columns: (1.6em, 1.9em, 1fr),
          column-gutter: 0.3em,
          align: (left + top, left + top, left + top),
          if option.label == none {
            numbering("A", index + 1)
          } else { option.label },
          choice-mark,
          option.body,
        )),
    )
  },
)

// Squared paper, 5 mm to a cell.
#let answer-grid(rows, cols, indent: 0em) = answer-space(
  indent: indent,
  table(
    columns: range(cols).map(_ => 5mm),
    rows: range(rows).map(_ => 5mm),
    stroke: 0.4pt + luma(72%),
    inset: 0pt,
    ..range(rows * cols).map(_ => []),
  ),
)

// An empty table for the student to fill in.
#let answer-table(rows, cols, indent: 0em) = answer-space(
  indent: indent,
  table(
    columns: range(cols).map(_ => 1fr),
    rows: range(rows).map(_ => 9mm),
    stroke: 0.5pt + luma(58%),
    ..range(rows * cols).map(_ => []),
  ),
)

// A run of questions under one heading. `marks` is the section's own total, never added into
// the paper's: where a student chooses, the two are different numbers.
#let section-heading(title, instructions, choose, marks) = block(
  width: 100%,
  above: 1.9em,
  below: 0.4em,
  breakable: false,
  sticky: true,
  {
    set par(justify: false)
    line(length: 100%, stroke: 0.7pt)
    v(0.55em)
    grid(
      columns: (1fr, auto),
      column-gutter: 0.6em,
      align: (left + bottom, right + bottom),
      if title == none { [] } else {
        text(size: 13pt, weight: "bold", hyphenate: false, title)
      },
      if marks == none { [] } else {
        text(size: 10pt, fill: luma(35%), str(marks) + " marks")
      },
    )
    if choose != none {
      v(0.4em)
      text(
        size: 10pt,
        style: "italic",
        "Answer " + str(choose) + " of the following questions.",
      )
    }
    if instructions != none {
      v(0.5em)
      instructions
    }
    v(0.55em)
    line(length: 100%, stroke: 0.4pt + luma(75%))
  },
)
