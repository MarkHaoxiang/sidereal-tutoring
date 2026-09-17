# Paper extraction across subjects

Four real AQA papers put through the live pipeline — Directus upload, `POST /api/documents`,
`POST /api/jobs/paper_extract` — to find where the canonical structure and the extraction hold
and where they break. 16 September 2026, `openrouter` backend, `anthropic/claude-sonnet-5`,
`SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS=48000`, no reasoning-effort dial (the run predates it).
One extraction attempt per paper; the mark schemes were ingested but not passed to the
extractor.

## Corpus

Downloaded from `https://filestore.aqa.org.uk/sample-papers-and-mark-schemes/2022/june/` into
`data/samples/` (git-ignored).

| File | Bytes | Pages | Pages with raster images |
| --- | --- | --- | --- |
| `AQA-74081-QP-JUN22.PDF` A-level Physics 7408/1 | 1,025,939 | 36 | 18 |
| `AQA-74081-MS-JUN22.PDF` mark scheme | 440,402 | 23 | |
| `AQA-75172-QP-JUN22.PDF` A-level Computer Science 7517/2 | 817,183 | 32 | 7 |
| `AQA-75172-MS-JUN22.PDF` mark scheme | 504,752 | 31 | |
| `AQA-77121-QP-JUN22.PDF` A-level English Literature A 7712/1 | 330,814 | 12 | 1 (page furniture) |
| `AQA-77121-MS-JUN22.PDF` mark scheme | 415,546 | 27 | |
| `AQA-83001H-QP-JUN22.PDF` GCSE Maths Higher 8300/1H | 1,324,956 | 32 | 19 |
| `AQA-83001H-MS-JUN22.PDF` mark scheme | 618,683 | 33 | |
| `AQA-75171-QP-JUN22.PDF` A-level Computer Science 7517/1 | 481,882 | 24 | — not extracted; kept as evidence for the skeleton-code finding |

## Results

| Paper | Pages | Ingested chars | Outcome | Questions found / actual | Marks found / stated | Model calls | Cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Physics 7408/1 | 36 | 23,186 | succeeded, rendered (10 pp) | 31 / 31 | 85 / 85 | 1 | $0.2336 |
| Computer Science 7517/2 | 32 | 23,062 | succeeded after two Typst repair rounds, rendered (10 pp) | 13 / 13 | 100 / 100 | 3 | $0.6105 |
| English Literature 7712/1 | 12 | 19,698 | succeeded, rendered (6 pp) | 7 / 7 | 175 offered / 75 answerable | 1 | $0.1031 |
| GCSE Maths 8300/1H | 32 | 12,044 | succeeded, rendered (6 pp) | 28 / 28 | 80 / 80 | 1 | $0.4917 |

Total for the four runs: **$1.4388**, from the papers' own `generated_from.usage`. The key's
`usage` went 0.748714 → 3.005738 over the same window, but another agent was spending against
the same key concurrently, so the per-job figures above are the accurate ones. Weekly limit
$100, $96.99 remaining at the end.

Tokens: Physics 14,699 in / 20,424 out (13,032 reasoning) · CS 32,998 / 54,448 (35,403) ·
English 11,442 / 8,018 (898) · Maths 9,870 / 47,192 (43,646).

Question counts and mark totals are the headline that flatters the pipeline: every paper's
question count is exact and three of four sum to the stated total to the mark. Everything below
is what that number hides.

## What the PDF-to-text step lost

`UploadIngester._read_pdf` calls pypdf's default `page.extract_text()`.

- **Stacked fractions are interleaved and unrecoverable.** GCSE Maths 24(a) is `6/a − 11/(4a)`;
  pypdf gives `Simplify fully     a` / `6  – a4` / `11`. Poppler's `pdftotext -layout` on the
  same page gives the numerators on one line and the denominators below, in the right columns.
- **Superscripts and subscripts are flattened onto the baseline.** Physics `⁴₂He` arrives as
  `4` / `2He`, `²³⁸₉₂U` as `238` / `  92U`.
- **Every table loses its grid.** The CS assembly instruction set (Table 1) reads as a single
  column with continuation lines indistinguishable from new rows; the CS truth table header
  arrives as `𝐀𝐀 𝐁𝐁 𝐀𝐀 + 𝐁𝐁 𝐀𝐀̅ 𝐁𝐁̅ …` (Word's bold-maths glyph doubling); the trace table
  collapses to `120 121 122 R0 R1 R2 R3` / `23 5` with its empty cells gone.
- **Ruled answer lines and answer boxes leave no trace at all** — they are vector graphics.
- **Every figure, graph, grid and diagram is absent**, leaving only the caption `Figure n`.
- **AQA's split question-number boxes arrive as `0 1` / `. 3`**, three lines apart from the text
  they label. The model reassembled these correctly in all four papers.
- Code listings survive well: the CS assembly program kept its lines and indentation.
- The English paper survives almost intact — the Othello extract and both unseen poems came
  through with speaker names and verse lineation preserved. It is the one paper that is
  genuinely text.

## Findings, in priority order

**1. Stacked maths is silently reconstructed wrong.** GCSE Maths 24(a) `6/a − 11/(4a)` was
stored as `$frac(a,6) - frac(a-4,11)$`; 24(b) `(y²−3y) × (y²+10y+21)/(y²−9)` was stored as
`$(y^2 - 3y) times frac(y+2, y^2 - 10y + 21)$`. Both render cleanly and confidently, and both
are different questions from the ones on the paper. Nothing in the pipeline can detect this.
*Change:* extract with a reader that keeps the page's two-dimensional arrangement. Poppler's
`pdftotext -layout` renders that page as `6   11` above `24 (a)   Simplify fully     –` above
`a   4a`, and 24(b) with numerator and denominator stacked around the rule — both recoverable.
Note that pypdf's own `extraction_mode="layout"` is *not* the fix: on that page it drops the
fraction glyphs altogether, leaving `24  (a)  Simplify fully` and nothing else. This is the
cheapest change here and the only one that addresses wrong content rather than missing content.

**2. Drawn content has nowhere to go.** 12 of 28 Maths questions, 6 of 13 CS questions and all 6
Physics Section A questions refer to a figure, graph, grid or table that is not in the
structure. The rendered Maths paper prints `23. On the grid, identify the region represented by
x > 3 and y > 1 and x + y ≤ 7. Label the region R. [3]` with no grid and no answer space.
*Change:* a `figure` node — `{label, page, file}` — referenced by a question or part, with the
page region cropped out of the source PDF and filed as a Directus file. The typeset service's
"no files, no network" invariant means `image` is currently refused; serving figures needs a
narrow, explicit exception rather than a general file resolver.

**3. There is no `section` and no choice.** English Literature has three sections and the student
answers three of seven questions. The extraction folded `Section A: Shakespeare. Answer one
question in this section.` and a bare `or` into question stems, and the rendered paper's
questions sum to 175 marks under a `total_marks` of 75. Physics lost `Section B` and its
`Each of Questions 07 to 31 is followed by four responses, A, B, C and D`.
*Change:* `Paper.sections: [{title, instructions, choose: int|null, questions: [...]}]`, and
`total_marks` validated against the answerable subset rather than the sum.

**4. There is no answer type.** Physics questions 07–31 (25 of 31) are four-option multiple
choice; Maths has 8 "circle your answer" questions; CS has 6 "shade one/two lozenges". All
became running prose: `Which two quantities have the base unit kg m² s⁻²? A kinetic energy and
momentum. B kinetic energy and Young modulus. C …`, and Maths 25(a)'s four options print as the
bare line `0 2 20 25`.
*Change:* `answer_type: lines | box | grid | essay | multiple_choice | table` with
`options: [{label, text}]`, and a `table` answer for the CS trace table and Physics data tables.

**5. Passages are stored intact and destroyed at render.** The 3,092-character Othello extract
and both unseen poems were stored with their line breaks. The rendered PDF prints them as one
prose paragraph — a stem is Typst markup, where a single newline is not a break. This is a
renderer gap, not a model failure: the information reached the database and the template threw
it away.
*Change:* a `passage` node at paper or question level, rendered in a verse/quote block that
keeps hard line breaks; and, since a Section A extract belongs to one question while the unseen
poems belong to the section, it needs to attach at both levels.

**6. Code listings flatten, and the maths warning causes a visible defect.** CS Figure 7's
assembly program became `LDR R0, 120; LDR R1, 121; MOV R3, \#0; loop: CMP R1, \#0; …` inside a
prose field, and the model's defensive backslash survives into the printed PDF as a literal
`\#0` where the paper says `#0` (six occurrences in that paper). Figure 8's functional
definitions went the same way.
*Change:* a `code` node rendered as preformatted text and escaped once by `render.rs`; and drop
"a `#` call is a compile error" from the extraction prompt — escaping is the renderer's job, and
telling the model about it makes the model do it twice.

**7. `answer_lines` is invented.** Ruled lines leave no text, so every value is the model's
estimate: Physics 3 got 5/4/2/5/8, Maths 22 got 15. The estimates are reasonable, which is the
problem — they are indistinguishable from read values.
*Change:* either derive answer space from marks in the renderer and drop the field from
extraction, or record in provenance that it was estimated.

**8. AQA's part labels are `NN.M`, not `a`/`b`.** Physics and CS parts came back labelled `1`,
`2`, `3` — matching the paper, contradicting the prompt's "its letter alone — `a`, `b`" — and
render as `(1)`, `(2)` where the paper says `01.1`. English numbered its questions `01` while
Physics numbered its `1`. Three of four papers disagreed with the prompt.
*Change:* stop prescribing a label alphabet; take what the paper prints, and let the template
stop adding brackets it cannot know are wanted.

**9. Mark schemes do not fit `MarkScheme` at all.** Physics' is a four-column table (question /
answers / additional comments / mark) behind fifteen pages of marking conventions. English
Literature's is a five-band level grid scored across AO1–AO5 (7/6/6/3/3 marks of 25) plus
indicative content — there is no per-part answer to store. `{label, answer, marks, notes}` holds
neither.
*Change:* `levels: [{band, marks, descriptors}]` and `objectives: [{code, marks}]` alongside the
existing per-part shape, or a decision that mark-scheme extraction covers the sciences and maths
only.

**10. Cost is driven by uncapped reasoning and by the repair loop, not by paper size.** GCSE
Maths — the smallest input at 12,044 characters — spent 43,646 of its 47,192 output tokens on
reasoning and cost $0.49, twice the 36-page Physics paper at $0.23. CS needed two Typst repair
rounds, tripling its calls to reach $0.61; the first repair did not clear the fault, and the
compiler reported the identical diagnostic again.
*Change:* the reasoning-effort dial now being added covers the first. The second argues for
validating the Typst markup of every text field locally — balanced `$`, no `\command` — before
the compiler sees the whole paper, so a repair round is spent on a fault the local check could
not catch.

**11. Companion documents are referenced and missing.** Physics tells the student to use a Data
and Formulae Booklet; GCSE Maths references an enclosed Formulae Sheet; CS Paper 1 (kept in the
corpus, not extracted) is written against a preliminary skeleton-code file the student has
already seen. Nothing links a paper to the documents it depends on.
*Change:* `Paper.companions: [document_id]`, filled by the tutor, so the reference is at least
resolvable.

## Is text-based extraction viable?

**For English Literature and Language, yes.** The paper is text; one raster image in twelve
pages, and it is page furniture. The extraction was the cheapest of the four ($0.10), exact on
question count, and lost nothing the PDF contained. What it needs is schema — sections, choice,
passages — not better input.

**For Physics, Computer Science and Maths, no.** Half the pages carry drawn content that the
text pipeline cannot see, and the failure is not confined to omission: finding 1 shows the text
route producing confidently wrong mathematics that survives validation, compilation and
rendering. A paper a tutor cannot hand to a student is a nuisance; a paper with a silently
altered question is worse than none.

Recommended order: (a) switch to layout-preserving text extraction now — `_read_pdf` is a
one-function change, and it is the only thing standing between a tutor and a wrong question;
poppler or PyMuPDF, not pypdf's layout mode; (b) add
`answer_type`, `section`/choice, `passage` and `code` to the canonical structure, since these
cost nothing at extraction time and are what the model is already trying to express in prose;
(c) move to page-image input — the PDF rendered page by page at ~150 dpi alongside the layout
text — for any paper whose pages carry images, and use the same page images to crop the figures
the structure will then be able to reference.

## Corpus identifiers

Kept in Directus as the test corpus.

| Paper | Document (question paper) | Document (mark scheme) | `papers` row | Job |
| --- | --- | --- | --- | --- |
| Physics 7408/1 | `d44bee73-c14a-4e2e-9611-601f6beea7da` | `6dc0d1e8-9b3f-442f-83aa-2618b3762a17` | `eda18eed-8c02-4f8c-bce7-b58a5f26c705` | `41f62eef-2f70-4d74-a121-a21353d0ddaf` |
| Computer Science 7517/2 | `25133743-86d3-47bd-a0e1-eac5bd5e1a7a` | `45647c41-8ea0-4d86-8573-850e2efd56dc` | `709bade4-f684-4374-aa94-0ee82899ddb2` | `576d6ade-e6c8-40cb-b3dc-ba89194603b8` |
| English Literature 7712/1 | `b8a3e8b3-a94d-4377-a802-3272d566f90d` | `e7a12d6b-fdd7-41b2-a3ef-2ae65633fdfa` | `653604f5-d3b8-401d-a091-2843736a456f` | `cca95bf2-dd58-4dc2-b27c-88668760c335` |
| GCSE Maths 8300/1H | `5e93eca4-8c09-49ae-9199-12530bf59b4c` | `b9c7d4ab-2775-4b41-adc6-e3ad4dfd5b2c` | `2e3c0de3-6093-4372-9f9f-12d5964bc758` | `5bcf6a48-2836-4593-8ef8-3ed283aa46ba` |

Each paper also wrote one `questions` row per top-level question: 31, 13, 7 and 28.
