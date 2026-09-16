// The house fragment layout: one question, or one field of markup, set exactly as it would be
// inside a paper but on a page as wide as the paper's text column and only as tall as it needs.
// `POST /render` returns `questions.typ`, `mark_scheme.typ`, this file, `#show: fragment` and
// the rendered node.

// The text column of an A4 paper, so a fragment breaks its lines where the paper does.
#let fragment-width = 210mm - 4.4cm

// Typst measures a line from cap height to baseline, so ascenders and the tops of inline maths
// sit above the page and descenders below it; 6pt is the most 11pt text overhangs by.
#let fragment-margin = 6pt

#let fragment(body) = {
  set page(
    width: fragment-width + fragment-margin * 2,
    height: auto,
    margin: fragment-margin,
  )
  set text(font: "New Computer Modern", size: 11pt, lang: "en")
  set par(justify: true, leading: 0.7em, spacing: 1.15em)
  show math.equation: set text(font: "New Computer Modern Math")

  body
}
