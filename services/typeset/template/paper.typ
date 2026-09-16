// The house exam-paper layout. `POST /render` returns `questions.typ`, this file, a
// `#show: paper.with(...)` line and the rendered questions — one source that compiles alone.

#let paper(
  title: "",
  source: none,
  board: none,
  year: none,
  time-minutes: none,
  total-marks: none,
  instructions: none,
  body,
) = {
  set document(title: title)
  set page(
    paper: "a4",
    margin: (x: 2.2cm, top: 2.2cm, bottom: 2.4cm),
    numbering: "1 / 1",
  )
  set text(font: "New Computer Modern", size: 11pt, lang: "en")
  set par(justify: true, leading: 0.7em, spacing: 1.15em)
  show math.equation: set text(font: "New Computer Modern Math")

  let overline = ()
  if board != none and board != "" { overline.push(board) }
  if year != none { overline.push(str(year)) }

  block(width: 100%, below: 0.8em, align(center, {
    if overline.len() > 0 {
      text(
        size: 10pt,
        tracking: 0.09em,
        fill: luma(30%),
        upper(overline.join(" · ")),
      )
      v(0.45em)
    }
    text(size: 17pt, weight: "bold", title)
    if source != none and source != "" {
      v(0.4em)
      text(size: 10pt, fill: luma(35%), source)
    }
  }))

  line(length: 100%, stroke: 0.7pt)

  let allowed = if time-minutes == none { "" } else {
    "Time allowed: " + str(time-minutes) + " minutes"
  }
  let total = if total-marks == none { "" } else {
    "Total: " + str(total-marks) + " marks"
  }
  if allowed != "" or total != "" {
    block(width: 100%, above: 0.7em, below: 0.9em, grid(
      columns: (1fr, 1fr),
      align: (left, right),
      text(size: 10pt, allowed),
      text(size: 10pt, total),
    ))
  }

  if instructions != none {
    block(
      width: 100%,
      above: 0.7em,
      below: 1.2em,
      fill: luma(96%),
      stroke: 0.5pt + luma(72%),
      radius: 3pt,
      inset: (x: 0.9em, y: 0.8em),
      {
        text(
          size: 9pt,
          weight: "bold",
          tracking: 0.08em,
          fill: luma(30%),
          "INSTRUCTIONS",
        )
        v(0.4em)
        set par(justify: false)
        instructions
      },
    )
  }

  body
}
