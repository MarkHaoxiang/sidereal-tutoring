"""A homework's questions, and the tutor's marks on the hand-in."""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from sidereal_core.directus import DirectusClient
from sidereal_core.models import (
    Collection,
    Homework,
    HomeworkFormat,
    HomeworkMarking,
    HomeworkQuestion,
    HomeworkStatus,
    Question,
)
from sidereal_core.typst_text import plain_text

# The template's own line, always at the head of a rendered sheet and never indented.
_SHOW = re.compile(r"^#show:", re.MULTILINE)


class QuestionText(BaseModel):
    """One question of a homework, readable: its Typst maths is turned into text."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    number: str | None = None
    marks: int | None = None
    text: str


def sheet_text(homework: Homework) -> str:
    """The sheet as the student received it: the house preamble off, its maths readable.

    A homework's questions are the ones it was generated from; the sheet is what the tutor
    edited and the student answered, and after an edit the two say different things.
    """
    content = (homework.content or "").strip()
    if homework.format is HomeworkFormat.TYPST:
        content = _body(content)
    return plain_text(content)


def _body(source: str) -> str:
    """Everything after the template's `#show:` call. The preamble is the renderer's, not work."""
    shown = [match.end() for match in _SHOW.finditer(source)]
    if not shown:
        return source
    return source[_call(source, shown[-1]) :].strip()


def _call(source: str, start: int) -> int:
    """Where the `#show:` line ends: after its arguments, or at the newline when it has none."""
    line = source.find("\n", start)
    opened = source.find("(", start)
    if opened == -1 or (line != -1 and opened > line):
        return len(source) if line == -1 else line + 1
    depth = 0
    for index in range(opened, len(source)):
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    return len(source)


async def ordered_questions(client: DirectusClient, homework_id: UUID) -> list[Question]:
    """The homework's questions in the order they were set: one `_in` query, not one per row."""
    links = await client.list_items(
        Collection.HOMEWORK_QUESTIONS,
        HomeworkQuestion,
        filter={"homework": {"_eq": str(homework_id)}},
        sort=["sort"],
    )
    ordered = sorted(links, key=lambda link: link.sort or 0)
    if not ordered:
        return []
    questions = await client.list_items(
        Collection.QUESTIONS,
        Question,
        filter={"id": {"_in": [str(link.question) for link in ordered]}},
    )
    by_id = {question.id: question for question in questions}
    return [question for link in ordered if (question := by_id.get(link.question)) is not None]


async def question_texts(client: DirectusClient, homework_id: UUID) -> list[QuestionText]:
    return [
        QuestionText(
            id=question.id,
            number=question.number,
            marks=question.marks,
            text=plain_text(question.text),
        )
        for question in await ordered_questions(client, homework_id)
    ]


async def mark_homework(
    client: DirectusClient, homework_id: UUID, marking: HomeworkMarking
) -> Homework:
    """File the marks and take the row to `marked`: one write, so a half-marked row cannot exist."""
    return await client.update_item(
        Collection.HOMEWORK,
        Homework,
        homework_id,
        {"marking": marking.model_dump(mode="json"), "status": HomeworkStatus.MARKED.value},
    )
