"""A homework's questions, and the tutor's marks on the hand-in."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from sidereal_core.directus import DirectusClient
from sidereal_core.models import (
    Collection,
    Homework,
    HomeworkMarking,
    HomeworkQuestion,
    HomeworkStatus,
    Question,
)
from sidereal_core.typst_text import plain_text


class QuestionText(BaseModel):
    """One question of a homework, readable: its Typst maths is turned into text."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    number: str | None = None
    marks: int | None = None
    text: str


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
