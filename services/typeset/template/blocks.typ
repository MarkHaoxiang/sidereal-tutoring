// The content blocks a question, a part or a mark-scheme entry can carry: an extract, a code
// listing, a data table, a figure. Concatenated before every layout, so a paper, a worksheet,
// a mark scheme and a fragment set them identically.

#let block-rule = 0.5pt + luma(74%)
#let block-fill = luma(97%)
#let caption-size = 9.5pt

// A string set line for line. It is a string, not content, so nothing in it is markup and
// nothing in it can execute; leading spaces are re-created as space so verse keeps its shape.
// Every parameter here avoids the name `text`, which is a function the layouts call.
#let verbatim(lines) = {
  lines
    .split("\n")
    .map(line => {
      let stripped = line.trim(at: start)
      box(width: (line.len() - stripped.len()) * 0.5em) + [#stripped]
    })
    .join(linebreak())
}

#let passage-block(title, extract, indent: 0em) = block(
  width: 100%,
  above: 1.0em,
  below: 1.0em,
  pad(left: indent, block(
    width: 100%,
    fill: block-fill,
    stroke: (left: 2pt + luma(70%)),
    inset: (left: 0.9em, rest: 0.8em),
    {
      set par(justify: false, leading: 0.65em, first-line-indent: 0em)
      if title != none {
        block(below: 0.6em, text(hyphenate: false, strong(title)))
      }
      verbatim(extract)
    },
  )),
)

// A question pointing at a passage printed once at the start of the paper. The title is a
// content block, which ends in a space, so nothing may follow it but a space.
#let passage-ref(title, indent: 0em) = block(
  width: 100%,
  above: 0.8em,
  below: 0.8em,
  pad(left: indent, text(
    size: 10pt,
    fill: luma(25%),
    [Printed at the start of this paper: #title],
  )),
)

#let code-block(language, listing, indent: 0em) = block(
  width: 100%,
  above: 1.0em,
  below: 1.0em,
  breakable: false,
  pad(left: indent, block(
    width: 100%,
    fill: block-fill,
    stroke: block-rule,
    inset: (x: 0.8em, y: 0.7em),
    {
      set text(size: 9.5pt)
      if language == none { raw(listing, block: true) } else {
        raw(listing, lang: language, block: true)
      }
    },
  )),
)

#let data-table(caption, header, rows, indent: 0em) = block(
  width: 100%,
  above: 1.0em,
  below: 1.0em,
  breakable: false,
  pad(left: indent, {
    set par(justify: false)
    let columns = if header != none { header.len() } else if rows.len() > 0 {
      rows.at(0).len()
    } else { 1 }
    table(
      columns: range(columns).map(_ => auto),
      stroke: block-rule,
      inset: (x: 0.55em, y: 0.45em),
      align: left + top,
      ..if header == none { () } else {
        header.map(cell => table.cell(fill: block-fill, strong(cell)))
      },
      ..rows.flatten(),
    )
    if caption != none {
      block(above: 0.5em, text(size: caption-size, fill: luma(35%), caption))
    }
  }),
)

// The only call that reads a file, and the only files that exist are the request's own assets,
// held in memory and keyed by name.
#let figure-block(asset, caption, width, indent: 0em) = block(
  width: 100%,
  above: 1.0em,
  below: 1.0em,
  breakable: false,
  pad(left: indent, align(center, {
    if width == none { image(asset) } else { image(asset, width: width) }
    if caption != none {
      block(above: 0.6em, text(size: caption-size, fill: luma(35%), caption))
    }
  })),
)
