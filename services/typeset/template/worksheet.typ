// The house worksheet layout — the structured successor to `homework.typ`. `POST /render`
// returns `questions.typ`, this file, a `#show: worksheet.with(...)` line and the questions.

#let worksheet(title: "", student: none, due: none, intro: none, body) = {
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

  block(width: 100%, below: 1.3em, {
    text(size: 16pt, weight: "bold", title)
    v(0.35em)
    if meta.len() > 0 {
      text(size: 10pt, fill: luma(35%), meta.join("   ·   "))
      v(0.45em)
    }
    line(length: 100%, stroke: 0.7pt)
  })

  if intro != none {
    block(width: 100%, below: 1.2em, {
      set par(justify: false)
      intro
    })
  }

  body
}
