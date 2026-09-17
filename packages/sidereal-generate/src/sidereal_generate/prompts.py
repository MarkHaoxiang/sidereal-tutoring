from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from typing import Any

from sidereal_core.canonical import CanonicalQuestion
from sidereal_core.models import Document, Question
from sidereal_core.typst_text import plain_text
from sidereal_ingest.transcribe import PaperQuestion

from sidereal_generate.chunks import QuestionStub
from sidereal_generate.models import GenerationRequest, MarkedHomework

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
_DATES = (
    " Every date below is printed with its own weekday. Work 'tomorrow', 'this week' and 'before "
    "your next lesson' out from those dates and from nothing else, and never name a weekday that "
    "is not printed beside its date."
)
_HOMEWORK_TASK = (
    "You produce a homework assignment for one student from their tutor's source material. "
)
_HOMEWORK_CRAFT = (
    " Pitch every question at the student's stated level. Give each question a worked "
    "answer the tutor can mark against, and set difficulty from 1 (recap) to 5 (stretch)."
)

HOMEWORK_PROMPT = f"{_HOMEWORK_TASK}{_AUDIENCE}{_MARKDOWN}{_HOMEWORK_CRAFT}{_DATES}"

HOMEWORK_TYPST_PROMPT = (
    f"{_HOMEWORK_TASK}{_AUDIENCE}{_HOMEWORK_CRAFT}{_DATES}"
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
    f"of work each point refers to, and end with one concrete next step.{_DATES}"
    " Where a hand-in is given below you have the questions as they were set, what the student "
    "wrote, the transcription of any working they photographed, and the tutor's marks. Work from "
    "those: quote what the student actually wrote, say which question each point is about, and "
    "account for the marks the tutor gave. Anything not in the hand-in you did not see — never "
    "praise or describe working that is not there, and say a question was left blank only when "
    "the hand-in shows it was."
)

PLAN_PROMPT = (
    "You produce a study plan for one student over a stated period. "
    f"{_AUDIENCE}{_MARKDOWN} Sequence topics so each builds on the last, and say what the tutor "
    f"should cover in each session rather than listing topics without a schedule.{_DATES}"
    " Finish the plan: a plan that stops part way through the period is of no use, so keep each "
    "week short enough that every week of the period is written."
)

_DRAWN = "a diagram, graph, grid, circuit, map, photograph, or a table printed as an image"
_TRANSCRIBING = (
    "You read one exam paper and return it as structure. You are transcribing, not writing: "
    "copy what the paper prints, in the order it prints it, and never answer, correct, improve "
    "or invent anything. Material that is not part of a question — a cover page, a formula "
    "sheet, page furniture — is left out."
)
_NUMBERING = (
    "Numbering: `number` and `label` are what the paper prints, copied as they stand — `01.1`, "
    "`24`, `a`, `i`. Do not renumber, do not relabel, and do not add brackets or a trailing "
    "dot: the template draws none the paper did not."
)
_PAGE_IMAGES = (
    "The pages are supplied as images, in order, and the text below them is the PDF's own text "
    "layer laid out in columns: a hint for spelling and wording, not the truth about anything "
    "drawn. Where the two disagree the page image wins. Ruled answer lines, answer boxes, grids "
    "and every figure exist only in the image."
)
_MATERIAL = (
    "an extract, a poem, a play scene, a program listing or a printed data table, set apart "
    "from the question's own wording"
)

# The paper is read in three kinds of call: a shape, then its questions in runs, then the
# material those questions print. One schema over the whole paper is a grammar the provider
# refuses to compile.
SKELETON_PROMPT = (
    f"{_TRANSCRIBING}\n"
    "This call is the paper's shape alone. Another call transcribes each question in full, so "
    "write no parts, no answer spaces and no working here.\n"
    f"{_NUMBERING}\n"
    "Sections: a run of questions under one heading is a `sections` entry carrying the "
    "heading's `title`, its `instructions`, and `choose` — how many of that section's questions "
    "the student answers. Top-level `questions` is for a paper with no sections, and for loose "
    "questions printed before the first one. Every question the paper asks appears exactly "
    "once, at the top level or inside one section, in the order the paper prints it.\n"
    "What is one question: wording a question's parts share is its `stem`, and each thing the "
    "student must do under it is a part, not a question of its own. A label the paper prints as "
    "`NN.M` — `01.1`, `01.2` — is part `M` of question `NN`, so the stub's `number` is `01`, "
    "written once however many such labels follow it, and `M` is another call's to return as a "
    "part label.\n"
    "Each question is one stub: `number` as the paper prints it, `marks` the figure in the "
    "margin where it carries one, `page` the page it starts on, `stem` one line saying what it "
    "is about — a label for it, not a transcription of it — and `has_material` true when the "
    f"question prints {_MATERIAL}. A diagram, a graph or a photograph is not material, and "
    "neither is an empty table the student fills in.\n"
    "`passages` carries every extract, poem or scene that several questions share, in full and "
    "verbatim — every line break and blank line as printed — each under an `id` those questions "
    "name. A passage only one question uses is left out here.\n"
    "`instructions` is the paper's own rubric; `time_minutes` and `total_marks` are what its "
    "front page states."
)
SKELETON_PAGES_PROMPT = f"{SKELETON_PROMPT}\n{_PAGE_IMAGES}"

QUESTION_BATCH_PROMPT = (
    f"{_TRANSCRIBING}\n"
    "The questions this call transcribes are listed below. Return those and no others, in the "
    "order listed, each in full.\n"
    f"{_NUMBERING} Parts nest one level only, so a part of a part has no parts of its own; fold "
    "a third level into the text above it. Wording a question's parts share is its `stem`; each "
    "thing the student must do is a part. `marks` is the figure in the margin, for the question "
    "when it carries one and for each part when they do.\n"
    "Answers: `answer` is the space the student writes in. `multiple_choice` carries the "
    "options the paper lists, each option's `label` being the letter the paper printed — leave "
    "it out and the renderer letters them. `lines` carries `lines`, `box` and `essay` carry "
    "`height_mm`, `grid` and `table` carry `rows` and `cols`, and `none` is a question the "
    "paper leaves no space for. 'Circle your answer', 'shade one lozenge', 'tick one box' and "
    "the like are `multiple_choice` with the printed options, never running prose — and the "
    "paper's own wording stays in the stem, because the renderer adds no instruction of its "
    "own. Ruled lines leave no text in a PDF, so a line count is your estimate — size it from "
    "the marks and from the space the paper gives, at most 60.\n"
    f"Material printed with a question — {_MATERIAL} — is another call's to return. "
    "Transcribe the wording alone and leave it out.\n"
    f"{_TYPST_MATHS_COPIED} Prose is written plainly, with "
    "`*bold*` and `_italic_` the only markup you need."
)
_FIGURES = (
    "Figures: `figures` is a list beside the questions, one entry per drawn thing a question "
    f"needs — {_DRAWN}. `page` is the paper's own page number, one of the pages you were shown, "
    "`bbox` is `[x0, y0, x1, y1]` normalised 0 to 1 from that page's top-left, generous enough "
    "to hold the whole drawing and its caption, `caption` is the paper's own caption where it "
    "prints one, and `question_number` and `part_label` say which node needs it. Go through the "
    "questions one at a time and decide of each whether it depends on something drawn."
)
QUESTION_BATCH_PAGES_PROMPT = f"{QUESTION_BATCH_PROMPT}\n{_PAGE_IMAGES}\n{_FIGURES}"
# Without page images nothing can be located, so the list is empty rather than guessed at.
QUESTION_BATCH_TEXT_PROMPT = (
    f"{QUESTION_BATCH_PROMPT}\n`figures` is empty: there are no page images to locate one on."
)

BLOCK_BATCH_PROMPT = (
    f"{_TRANSCRIBING}\n"
    "This call returns the material the questions listed below print, and nothing else: their "
    "wording is already transcribed. Every block names the `question_number` it belongs to and "
    "the `part_label` under which it is printed, or a null label when it stands above the "
    "parts.\n"
    "An extract, a poem or a play scene is a `passage` block; where the paper prints it once "
    "for several questions it is already in the paper's `passages` and each question carries a "
    "`passage_ref` block naming its `id` instead. A passage's `text` is verbatim — every line "
    "break and blank line as printed, and nothing in it is markup. A program listing is a "
    "`code` block with its `language`, verbatim too, never prose. A printed data table is a "
    "`table` block with its `header` and `rows`; an empty table for the student to fill in is "
    "not material and is left out. Return no blocks at all rather than inventing one.\n"
    f"{_TYPST_MATHS_COPIED}"
)
BLOCK_BATCH_PAGES_PROMPT = f"{BLOCK_BATCH_PROMPT}\n{_PAGE_IMAGES}"

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

# The drawn pages are the ingest layer's own reading of the PDF, not the model's judgement.
DRAWN_PAGES = (
    f"Pages {{pages}} carry drawn content — {_DRAWN}. A question that depends on something "
    "drawn there needs a `figures` entry."
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

# Named here rather than taken from the locale, which decides what `strftime` writes.
WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

HOMEWORK_TOOL = "emit_homework"
FEEDBACK_TOOL = "emit_feedback"
PLAN_TOOL = "emit_plan"
PAPER_TOOL = "emit_paper"
SKELETON_TOOL = "emit_paper_shape"
QUESTIONS_TOOL = "emit_questions"
BLOCKS_TOOL = "emit_blocks"
MARK_SCHEME_TOOL = "emit_mark_scheme"
SCAN_TOOL = "emit_transcription"
PAPER_REPAIR = (
    "The paper these questions came from does not compile. Return these same questions again "
    "with only the maths corrected: every other field must come back byte for byte as it is. Do "
    "not answer, reword, add or drop a question. The compiler stops at the first fault it meets, "
    "so fix every one it names *and* every other instance of the same mistake in what you are "
    f"shown — one round has to clear the whole class. {_TYPST_MATHS_COPIED} `figures` is empty: "
    "a repair locates nothing.\n"
    "The questions follow, then what the compiler reported."
)
MARK_SCHEME_REPAIR = (
    "The mark scheme these answers came from does not compile. Return these same answers again "
    "with only the maths corrected: every other field must come back byte for byte as it is. Do "
    "not reword, add or drop an answer. The compiler stops at the first fault it meets, so fix "
    "every one it names *and* every other instance of the same mistake in what you are shown — "
    f"one round has to clear the whole class. {_TYPST_MATHS_COPIED}\n"
    "The answers follow, then what the compiler reported."
)
BATCH_RETRY = (
    "Your previous answer did not fit the structure. Answer this call again, corrected, and "
    "return the same questions. The validator reported:"
)
MARK_SCHEME_MISSING = (
    "Your previous answer had no entry for {named}. Answer this call again with one entry per "
    "question in the list below, under the number the list prints. The scheme marks every "
    "question the paper asks, so an entry you did not find is one to look for again — it may be "
    "printed under a heading, in a table, or on a later page than the questions around it."
)
MARK_SCHEME_PARTS_MISSING = (
    "Your previous answer left {named} unanswered. Answer this call again with one `parts` entry "
    "per label the list below prints under a question, under the label the list prints, and with "
    "`answer` on the entry itself for a question the list prints no labels for. An answer you did "
    "not find is one to look for again — it may be printed in a table, under a heading, or on a "
    "later page than the answers around it."
)
FIGURE_WORDING = (
    "Your previous answer left {named} with a figure and no wording at all. Answer this call "
    "again with every question and part transcribed in full. A question's wording is printed on "
    "the page beside the drawing: transcribe it from the page. A figure is a picture the paper "
    "prints alongside the words, never the place a question's only text is left."
)


def render_questions(questions: Sequence[PaperQuestion]) -> str:
    """The paper's questions, as the numbers a transcription may be filed under."""
    return "\n".join(
        f'<question number="{question.number}">{question.stem or ""}</question>'
        for question in questions
    )


def render_document(document: Document) -> str:
    return _tagged("document", document)


def render_pages(sent: Sequence[int], drawn: Sequence[int] = ()) -> str:
    """Which of the paper's pages went up as images, so a figure can name one by number."""
    if not sent:
        return ""
    lines = [
        (
            f"The page images are pages {page_numbers(sent)} of the paper, in that order. A "
            "page number you write is the paper's own, never the position of the image."
        )
    ]
    inside = [page for page in drawn if page in set(sent)]
    if inside:
        lines.append(DRAWN_PAGES.format(pages=page_numbers(inside)))
    return f"<pages>\n{' '.join(lines)}\n</pages>"


def render_wanted(stubs: Sequence[QuestionStub]) -> str:
    """The questions one call is asked for, by the number and page the shape gave them."""
    listed = "\n".join(
        f'<question number="{stub.number}" page="{stub.page}">{stub.stem}</question>'
        for stub in stubs
    )
    return f"<wanted>\n{listed}\n</wanted>"


def page_numbers(drawn: Sequence[int]) -> str:
    return ", ".join(str(page) for page in drawn)


def render_mark_scheme(document: Document, questions: Sequence[CanonicalQuestion]) -> str:
    """The scheme's text, under the numbers and labels the paper itself printed."""
    numbering = "\n".join(_numbering(questions))
    return f"{_tagged('mark_scheme', document)}\n<paper>\n{numbering}\n</paper>"


def _numbering(questions: Sequence[CanonicalQuestion]) -> Iterator[str]:
    """One line per node a mark scheme may answer, carrying the name it must answer by."""
    for question in questions:
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
        "<dates>",
        f"today: {dated(request.today, 'unstated')}",
        f"next lesson: {dated(request.session_date, 'none')}",
        "</dates>",
    ]
    parts.extend(render_homework(handed_in) for handed_in in request.homework)
    if request.period_start or request.period_end:
        parts.append(
            f"<period>{dated(request.period_start, 'unstated')} to "
            f"{dated(request.period_end, 'unstated')}</period>"
        )
    if request.instructions:
        parts.append(f"<instructions>{request.instructions}</instructions>")
    parts.extend(
        f'<document id="{document.id}" kind="{document.kind.value}" '
        f'title="{document.title}">\n{document.text or ""}\n</document>'
        for document in request.documents
    )
    return "\n".join(parts)


def dated(day: date | None, absent: str) -> str:
    """A date with its weekday printed beside it: a model asked to work one out gets it wrong."""
    return absent if day is None else f"{day.isoformat()} ({WEEKDAYS[day.weekday()]})"


def render_homework(handed_in: MarkedHomework) -> str:
    """One hand-in: what was set, what the student wrote, and how the tutor marked it."""
    homework = handed_in.homework
    due = dated(homework.due_on, "none")
    lines = [f'<homework title="{homework.title}" status="{homework.status.value}" due="{due}">']
    if handed_in.questions:
        lines.append("<questions>")
        lines.extend(_question(question) for question in handed_in.questions)
        lines.append("</questions>")
    lines.append(f"<submission>{homework.submission or 'nothing was typed in'}</submission>")
    lines.append(_transcription(homework.submission_transcription))
    lines.append(_marking(homework.marking))
    lines.append("</homework>")
    return "\n".join(line for line in lines if line)


def _question(question: Question) -> str:
    number = f' number="{question.number}"' if question.number else ""
    marks = "" if question.marks is None else f' marks="{question.marks}"'
    return f"<question{number}{marks}>{plain_text(question.text)}</question>"


def _transcription(transcription: dict[str, Any] | None) -> str:
    """The photographed working, or the sentence that says there is none to read."""
    text = (transcription or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        return "<working>no photograph of working was handed in</working>"
    confidence = (transcription or {}).get("confidence")
    read = f' read="{confidence}"' if isinstance(confidence, str) else ""
    return f"<working{read}>{text}</working>"


def _marking(marking: dict[str, Any] | None) -> str:
    if not marking:
        return "<marking>the tutor has not marked this yet</marking>"
    awarded = marking.get("total_awarded")
    available = marking.get("total_available")
    questions = marking.get("questions")
    lines = [f'<marking total="{awarded} out of {available}">']
    lines.extend(
        _marked(question)
        for question in (questions if isinstance(questions, list) else [])
        if isinstance(question, dict)
    )
    comment = marking.get("comment")
    if isinstance(comment, str) and comment.strip():
        lines.append(f"<comment>{comment}</comment>")
    lines.append("</marking>")
    return "\n".join(lines)


def _marked(question: dict[str, Any]) -> str:
    comment = question.get("comment")
    return (
        f'<question number="{question.get("number")}" '
        f'marks="{question.get("marks_awarded")} out of {question.get("marks_available")}">'
        f"{comment if isinstance(comment, str) else ''}</question>"
    )
