from __future__ import annotations

from sidereal_core.models import Document

from sidereal_generate.models import GenerationRequest

_TYPST_MATHS = (
    "Maths is Typst, not LaTeX: `$x^2 - 5x + 6$` inline and `$ ... $` with spaces inside the "
    "delimiters for a display line. Use `frac(a, b)` or `a / b`, `sqrt(x)`, `integral`, `sum`, "
    "`pi`, `alpha`, `->`, `<=`. A backslash command such as `\\frac` is a compile error, and so "
    "is a `#` call: a field is text, never Typst code. Letters written together are one name, so "
    'a segment, product or pair of points is `$P Q$` or `$"PQ"$` — `$PQ$` is an unknown variable '
    "and will not compile."
)
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
    "sheet, page furniture — is left out. If the source carries no mark scheme, return null for "
    "it rather than writing one.\n"
    "Numbering: `number` is the question's own label and nothing else — `1`, `2`, `12`. A part's "
    "`label` is its letter alone — `a`, `b` — and a part of a part is its roman numeral alone — "
    "`i`, `ii`. Never `(a)`, never `1.`: the template draws the brackets. Parts nest one level "
    "only, so a part of a part has no parts of its own; fold a third level into the text above "
    "it. Wording a question's parts share is its `stem`; each thing the student must do is a "
    "part. `marks` is the figure in the margin, for the question when it carries one and for "
    "each part when they do. `answer_lines` is how many ruled lines the student's working needs, "
    "at most 60, and is left null where the paper gives no answer space.\n"
    f"{_TYPST_MATHS} Prose is written plainly, with "
    "`*bold*` and `_italic_` the only markup you need.\n"
    "A mark scheme answers the paper by the same numbers and labels, and its `marks` say how "
    "the marks for a part are earned."
)

HOMEWORK_TOOL = "emit_homework"
FEEDBACK_TOOL = "emit_feedback"
PLAN_TOOL = "emit_plan"
PAPER_TOOL = "emit_paper"
PAPER_REPAIR = (
    "The paper you returned does not compile. Return the whole structure again with only the "
    "maths corrected: every other field must come back byte for byte as it is. Do not answer, "
    "reword, add or drop a question. The compiler stops at the first fault it meets, so fix "
    "every one it names *and* every other instance of the same mistake anywhere in the paper — "
    "one round has to clear the whole class. "
    f"{_TYPST_MATHS}\n"
    "The compiler reported:"
)
PAPER_RETRY = (
    "Your previous answer did not fit the structure. Return the whole paper again, corrected. "
    "The validator reported:"
)


def render_document(document: Document, mark_scheme: Document | None = None) -> str:
    """The paper, and the mark scheme beside it when the tutor filed one."""
    parts = [_tagged("document", document)]
    if mark_scheme is not None:
        parts.append(_tagged("mark_scheme", mark_scheme))
    return "\n".join(parts)


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
