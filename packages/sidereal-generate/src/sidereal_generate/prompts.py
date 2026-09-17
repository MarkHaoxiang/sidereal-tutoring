from __future__ import annotations

from collections.abc import Iterator, Sequence

from sidereal_core.canonical import CanonicalPaper
from sidereal_core.models import Document
from sidereal_ingest.transcribe import PaperQuestion

from sidereal_generate.models import GenerationRequest

_MATHS_HEAD = (
    "Maths is Typst, not LaTeX: `$x^2 - 5x + 6$` inline and `$ ... $` with spaces inside the "
    "delimiters for a display line. Use `frac(a, b)` or `a / b`, `sqrt(x)`, `integral`, `sum`, "
    "`pi`, `alpha`, `->`, `<=`. A backslash command such as `\\frac` is a compile error"
)
_MATHS_TAIL = (
    " Letters written together are one name, so "
    'a segment, product or pair of points is `$P Q$` or `$"PQ"$` — `$PQ$` is an unknown variable '
    "and will not compile."
)
_TYPST_MATHS = (
    f"{_MATHS_HEAD}, and so is a `#` call: a field is text, never Typst code.{_MATHS_TAIL}"
)
# The renderer escapes; a model warned about `#` escapes it too, and `#0` prints as `\#0`.
_TYPST_MATHS_COPIED = f"{_MATHS_HEAD}.{_MATHS_TAIL}"
_AUDIENCE = (
    "You write for a private tutor and their student. Plain language, no jargon, no filler. "
    "Use only the material you are given; if it does not cover something, leave it out rather "
    "than inventing it."
)
_MARKDOWN = " Write content as markdown."
_HOMEWORK_TASK = (
    "You produce a homework assignment for one student from their tutor's source material. "
)
_HOMEWORK_CRAFT = (
    " Pitch every question at the student's stated level. Give each question a worked "
    "answer the tutor can mark against, and set difficulty from 1 (recap) to 5 (stretch)."
)

HOMEWORK_PROMPT = f"{_HOMEWORK_TASK}{_AUDIENCE}{_MARKDOWN}{_HOMEWORK_CRAFT}"

HOMEWORK_TYPST_PROMPT = (
    f"{_HOMEWORK_TASK}{_AUDIENCE}{_HOMEWORK_CRAFT}"
    " `content` is a Typst document body and nothing else. It is placed inside the tutor's "
    "house template, so write no preamble: no `#import`, no `@preview` package, no `#set` or "
    "`#show` rule, no `#set page`, no title and no student name — the template supplies all of "
    "that. Two helpers are already in scope and are the only ones you may call: `#question[...]` "
    "opens a numbered question, and `#answerlines(n)` leaves n ruled lines for the student's "
    "working. Follow every `#question[...]` with an `#answerlines(n)` sized to the work it asks "
    f"for. {_TYPST_MATHS} Ordinary prose is written plainly; `*bold*` and "
    "`_italic_` are the only markup you need. The worked answers go in the `questions` list, "
    "never in `content`: the student's copy is what you are writing."
)

FEEDBACK_PROMPT = (
    "You produce written feedback on one student's recent work for their tutor to send. "
    f"{_AUDIENCE}{_MARKDOWN} Say what went well before what to work on, name the specific piece "
    "of work each point refers to, and end with one concrete next step."
)

PLAN_PROMPT = (
    "You produce a study plan for one student over a stated period. "
    f"{_AUDIENCE}{_MARKDOWN} Sequence topics so each builds on the last, and say what the tutor "
    "should cover in each session rather than listing topics without a schedule."
)

PAPER_PROMPT = (
    "You read one exam paper and return it as structure. You are transcribing, not writing: "
    "copy every question as it stands, in the order it stands in, and never answer, correct, "
    "improve or invent one. Material that is not part of a question — a cover page, a formula "
    "sheet, page furniture — is left out.\n"
    "Numbering: `number` and `label` are what the paper prints, copied as they stand — `01.1`, "
    "`24`, `a`, `i`. Do not renumber, do not relabel, and do not add brackets or a trailing "
    "dot: the template draws none the paper did not. Parts nest one level only, so a part of a "
    "part has no parts of its own; fold a third level into the text above it. Wording a "
    "question's parts share is its `stem`; each thing the student must do is a part. `marks` is "
    "the figure in the margin, for the question when it carries one and for each part when "
    "they do.\n"
    "Sections: a run of questions under one heading is a `sections` entry carrying the "
    "heading's `title`, its `instructions`, and `choose` — how many of that section's questions "
    "the student answers. Top-level `questions` is for a paper with no sections, and for loose "
    "questions printed before the first one.\n"
    "Answers: `answer` is the space the student writes in. `multiple_choice` carries the "
    "options the paper lists, each option's `label` being the letter the paper printed — leave "
    "it out and the renderer letters them. `lines` carries `lines`, `box` and `essay` carry "
    "`height_mm`, `grid` and `table` carry `rows` and `cols`, and `none` is a question the "
    "paper leaves no space for. 'Circle your answer', 'shade one lozenge', 'tick one box' and "
    "the like are `multiple_choice` with the printed options, never running prose — and the "
    "paper's own wording stays in the stem, because the renderer adds no instruction of its "
    'own. `answer_lines` is the deprecated spelling of `{"type": "lines"}`: use `answer`, '
    "and never send both for one node. Ruled lines leave no text in a PDF, so a line count is "
    "your estimate — size it from the marks and from the space the paper gives, at most 60.\n"
    "Blocks: the material between a stem and its parts. An extract, a poem or a play scene is a "
    "`passage` block on the question that uses it; where several questions share one, it is a "
    "`passages` entry on the paper and each of those questions carries a `passage_ref` block "
    "naming its `id`. A passage's `text` is verbatim — every line break and blank line as "
    "printed, and nothing in it is markup. A program listing is a `code` block with its "
    "`language`, verbatim too, never prose. A printed data table is a `table` block with its "
    "`header` and `rows`; an empty table for the student to fill in is an `answer` of type "
    "`table` instead.\n"
    "Figures: `figures` is a list beside the paper, one entry per drawn thing a question needs "
    "— a diagram, graph, grid, circuit, map, photograph, or a table printed as an image. `page` "
    "is the page image's own number, `bbox` is `[x0, y0, x1, y1]` normalised 0 to 1 from that "
    "page's top-left, generous enough to hold the whole drawing and its caption, `caption` is "
    "the paper's own caption where it prints one, and `question_number` and `part_label` say "
    "which node needs it. Put no `figure` block in the structure yourself: the app crops each "
    "region and places it.\n"
    f"{_TYPST_MATHS_COPIED} Prose is written plainly, with "
    "`*bold*` and `_italic_` the only markup you need."
)

MARK_SCHEME_PROMPT = (
    "You read one mark scheme and return it as structure. You are transcribing, not writing: "
    "copy each answer as it stands, and never solve, correct, improve or invent one. Material "
    "that is not an answer — a cover page, grade boundaries, page furniture — is left out.\n"
    "The paper's own numbers and labels are listed below the scheme, and they are the only "
    "names you may use: copy `number` and `label` from that list rather than from the way the "
    "scheme prints them, and leave out an entry the list has not got. A question the scheme "
    "does not answer is left out too.\n"
    "`answer` is what earns the marks, `marks` is how many, and `notes` is the scheme's own "
    "guidance to the marker — 'allow ecf', 'accept 3.1 to 3.2' — never your own. A question "
    "whose parts are marked separately carries one `parts` entry per label; one marked as a "
    "whole carries `answer`.\n"
    f"{_TYPST_MATHS_COPIED} Prose is written plainly, with "
    "`*bold*` and `_italic_` the only markup you need."
)

_DRAWN = "a diagram, graph, grid, circuit, map, photograph, or a table printed as an image"

PAPER_PAGES_PROMPT = (
    f"{PAPER_PROMPT}\n"
    "The pages are supplied as images, in order, and the text below them is the PDF's own text "
    "layer laid out in columns: a hint for spelling and wording, not the truth about anything "
    "drawn. Where the two disagree the page image wins. Ruled answer lines, answer boxes, "
    "grids and every figure exist only in the image.\n"
    f"Go through the questions one at a time and decide of each whether it depends on {_DRAWN} "
    "printed on the page. Return a `figures` entry for every one that does, before you finish."
)

# The drawn pages are the ingest layer's own reading of the PDF, not the model's judgement.
DRAWN_PAGES = (
    f"These pages carry drawn content — {_DRAWN}: {{pages}}. Every question that depends on "
    "something drawn there needs a `figures` entry, so returning none at all for these pages "
    "is almost certainly wrong."
)
PAPER_FIGURES_RETRY = (
    f"You returned no figures, but these pages carry drawn content — {_DRAWN}: {{pages}}. "
    "Return the whole paper again, unchanged except for `figures`: one entry per drawn thing a "
    "question needs, `page` and `bbox` locating it on the page image and `question_number` and "
    "`part_label` naming the node that needs it. Where a page's drawing really is page "
    "furniture and no question needs it, return no entry for that page."
)

_TRANSCRIBE = (
    "You transcribe handwritten pages. You are copying them out, not marking them: never solve, "
    "correct, finish or comment on the work, and never add a step the page does not have. Keep "
    "the writer's own order, line by line and page by page. Anything you cannot read is `[?]` in "
    "place of the word or the line; work the writer crossed out is left out."
)
_TRANSCRIBE_CONFIDENCE = (
    "`confidence` is how much of the writing you could read: `high` when nearly all of it, "
    "`medium` when a little of it is a guess, `low` when much of it is."
)

SCAN_PROMPT = (
    f"{_TRANSCRIBE} `text` is the whole transcription as markdown, with a `## Page n` heading "
    f"for each page. {_TYPST_MATHS} `questions` is empty: these pages answer no paper. "
    f"{_TRANSCRIBE_CONFIDENCE}"
)

SCAN_SOLUTIONS_PROMPT = (
    f"{_TRANSCRIBE} The pages are one student's answers to the paper whose questions are listed "
    "below. `text` is the whole transcription as markdown in page order. `questions` is that same "
    "working split up: one entry per question the pages answer, in the paper's order, `number` "
    "being the paper's own number and nothing else. Use only the numbers listed; leave out a "
    "question the pages do not answer, and where the working's number is a guess say so in "
    f"`note`. {_TYPST_MATHS} {_TRANSCRIBE_CONFIDENCE} Each question carries its own."
)

HOMEWORK_TOOL = "emit_homework"
FEEDBACK_TOOL = "emit_feedback"
PLAN_TOOL = "emit_plan"
PAPER_TOOL = "emit_paper"
MARK_SCHEME_TOOL = "emit_mark_scheme"
SCAN_TOOL = "emit_transcription"
PAPER_REPAIR = (
    "The paper you returned does not compile. Return the whole structure again with only the "
    "maths corrected: every other field must come back byte for byte as it is. Do not answer, "
    "reword, add or drop a question. The compiler stops at the first fault it meets, so fix "
    "every one it names *and* every other instance of the same mistake anywhere in the paper — "
    "one round has to clear the whole class. "
    f"{_TYPST_MATHS_COPIED}\n"
    "The compiler reported:"
)
MARK_SCHEME_REPAIR = (
    "The mark scheme you returned does not compile. Return the whole structure again with only "
    "the maths corrected: every other field must come back byte for byte as it is. Do not "
    "reword, add or drop an answer. The compiler stops at the first fault it meets, so fix "
    "every one it names *and* every other instance of the same mistake anywhere in the scheme — "
    "one round has to clear the whole class. "
    f"{_TYPST_MATHS_COPIED}\n"
    "The compiler reported:"
)
PAPER_RETRY = (
    "Your previous answer did not fit the structure. Return the whole paper again, corrected. "
    "The validator reported:"
)
MARK_SCHEME_RETRY = (
    "Your previous answer did not fit the structure. Return the whole mark scheme again, "
    "corrected. The validator reported:"
)


def render_questions(questions: Sequence[PaperQuestion]) -> str:
    """The paper's questions, as the numbers a transcription may be filed under."""
    return "\n".join(
        f'<question number="{question.number}">{question.stem or ""}</question>'
        for question in questions
    )


def render_document(document: Document, drawn: Sequence[int] = ()) -> str:
    text = _tagged("document", document)
    if not drawn:
        return text
    return f"{text}\n<drawn_pages>\n{DRAWN_PAGES.format(pages=page_numbers(drawn))}\n</drawn_pages>"


def page_numbers(drawn: Sequence[int]) -> str:
    return ", ".join(str(page) for page in drawn)


def render_mark_scheme(document: Document, paper: CanonicalPaper) -> str:
    """The scheme's text, under the numbers and labels the paper itself printed."""
    numbering = "\n".join(_numbering(paper))
    return f"{_tagged('mark_scheme', document)}\n<paper>\n{numbering}\n</paper>"


def _numbering(paper: CanonicalPaper) -> Iterator[str]:
    """One line per node a mark scheme may answer, carrying the name it must answer by."""
    sectioned = (question for section in paper.sections for question in section.questions)
    for question in (*paper.questions, *sectioned):
        yield f'<question number="{question.number}"{_marks(question.marks)}/>'
        for part in question.parts:
            if not part.parts:
                yield (
                    f'<part number="{question.number}" label="{part.label}"{_marks(part.marks)}/>'
                )
                continue
            # A mark scheme part carries no parts of its own, so a sub-part is one label.
            for sub in part.parts:
                yield (
                    f'<part number="{question.number}" label="{part.label}({sub.label})"'
                    f"{_marks(sub.marks)}/>"
                )


def _marks(marks: int | None) -> str:
    return "" if marks is None else f' marks="{marks}"'


def _tagged(tag: str, document: Document) -> str:
    return (
        f'<{tag} id="{document.id}" kind="{document.kind.value}" title="{document.title}">\n'
        f"{document.text or ''}\n</{tag}>"
    )


def render(request: GenerationRequest) -> str:
    student = request.student
    parts = [
        "<student>",
        f"name: {student.name}",
        f"level: {student.level or 'unstated'}",
        f"subjects: {', '.join(student.subjects) or 'unstated'}",
        f"notes: {student.notes or 'none'}",
        "</student>",
    ]
    if request.period_start or request.period_end:
        parts.append(
            f"<period>{request.period_start or 'unstated'} to "
            f"{request.period_end or 'unstated'}</period>"
        )
    if request.instructions:
        parts.append(f"<instructions>{request.instructions}</instructions>")
    parts.extend(
        f'<document id="{document.id}" kind="{document.kind.value}" '
        f'title="{document.title}">\n{document.text or ""}\n</document>'
        for document in request.documents
    )
    return "\n".join(parts)
