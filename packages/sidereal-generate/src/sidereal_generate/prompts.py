from __future__ import annotations

from sidereal_generate.models import GenerationRequest

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
    "for. Write maths in Typst syntax, not LaTeX: `$x^2 - 5x + 6$` inline and `$ ... $` on its "
    "own line for display, `frac(a, b)`, `sqrt(x)`, `integral`, `alpha`. A backslash command "
    "such as `\\frac` is a compile error. Ordinary prose is written plainly; `*bold*` and "
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

HOMEWORK_TOOL = "emit_homework"
FEEDBACK_TOOL = "emit_feedback"
PLAN_TOOL = "emit_plan"


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
