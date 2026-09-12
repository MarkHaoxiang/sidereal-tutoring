// The house homework template. `POST /template` returns this file, then a
// `#show: homework.with(...)` line, then the body — so the result compiles on its own.

#let question-counter = counter("sidereal-question")

#let question(body) = {
  question-counter.step()
  block(
    width: 100%,
    above: 1.15em,
    below: 0.75em,
    grid(
      columns: (1.9em, 1fr),
      column-gutter: 0.4em,
      align: (right + top, left + top),
      strong[#context question-counter.display().],
      body,
    ),
  )
}

#let answerlines(n) = block(
  width: 100%,
  above: 0.7em,
  below: 1.1em,
  stack(
    spacing: 1.6em,
    ..range(n).map(_ => line(length: 100%, stroke: 0.4pt + luma(65%))),
  ),
)

#let homework(title: "", student: none, due: none, body) = {
  set document(title: title)
  set page(
    paper: "a4",
    margin: (x: 2.2cm, top: 2.2cm, bottom: 2.4cm),
    numbering: "1 / 1",
  )
  set text(font: "New Computer Modern", size: 11pt, lang: "en")
  set par(justify: true, leading: 0.7em, spacing: 1.15em)
  show math.equation: set text(font: "New Computer Modern Math")

  let meta = ()
  if student != none and student != "" { meta.push("Student: " + student) }
  if due != none and due != "" { meta.push("Due: " + due) }

  block(width: 100%, below: 1.5em, {
    text(size: 16pt, weight: "bold", title)
    v(0.35em)
    if meta.len() > 0 {
      text(size: 10pt, fill: luma(35%), meta.join("   ·   "))
      v(0.45em)
    }
    line(length: 100%, stroke: 0.7pt)
  })

  body
}
