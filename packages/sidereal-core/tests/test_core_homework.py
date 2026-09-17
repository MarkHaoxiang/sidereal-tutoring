from __future__ import annotations

from typing import Any
from uuid import UUID

from sidereal_core.homework import mark_homework, ordered_questions, question_texts
from sidereal_core.models import Collection, HomeworkMarking, HomeworkStatus, MarkedQuestion
from sidereal_core.testing import FakeDirectus

STEMS = [
    "A uniform plank $A B$ has length $4.0$ m.",
    "Find the moment about $P$ when the force acts at $30°$.",
]


def seeded(fake: FakeDirectus) -> str:
    """One homework with its two questions linked out of order, as sorting must correct."""
    student = fake.seed(Collection.STUDENTS, {"name": "Leo"})
    homework = fake.seed(
        Collection.HOMEWORK,
        {"student": student["id"], "title": "Moments", "content": "", "status": "submitted"},
    )
    for position, stem in reversed(list(enumerate(STEMS, start=1))):
        question = fake.seed(
            Collection.QUESTIONS, {"text": stem, "number": str(position), "marks": 3}
        )
        fake.seed(
            Collection.HOMEWORK_QUESTIONS,
            {"homework": homework["id"], "question": question["id"], "sort": position},
        )
    return str(homework["id"])


async def test_the_questions_come_back_in_the_order_they_were_set() -> None:
    fake = FakeDirectus()
    homework_id = seeded(fake)

    async with fake.client() as client:
        questions = await ordered_questions(client, UUID(homework_id))

    assert [question.number for question in questions] == ["1", "2"]


async def test_a_homework_with_no_questions_asks_for_none() -> None:
    fake = FakeDirectus()
    student = fake.seed(Collection.STUDENTS, {"name": "Leo"})
    homework = fake.seed(
        Collection.HOMEWORK, {"student": student["id"], "title": "Moments", "content": ""}
    )

    async with fake.client() as client:
        assert await ordered_questions(client, UUID(homework["id"])) == []

    assert [request.url.path for request in fake.requests] == ["/items/homework_questions"]


async def test_a_question_reads_as_text_rather_than_as_typst() -> None:
    fake = FakeDirectus()
    homework_id = seeded(fake)

    async with fake.client() as client:
        questions = await question_texts(client, UUID(homework_id))

    assert questions[0].text == "A uniform plank AB has length 4.0 m."
    assert questions[0].marks == 3


async def test_marking_files_the_totals_and_takes_the_row_to_marked() -> None:
    fake = FakeDirectus()
    homework_id = seeded(fake)
    marking = HomeworkMarking.over(
        [
            MarkedQuestion(number="1", marks_awarded=3, marks_available=3),
            MarkedQuestion(number="2", marks_awarded=1, marks_available=3, comment="No units."),
        ],
        comment="Say which point you take moments about.",
    )

    async with fake.client() as client:
        marked = await mark_homework(client, UUID(homework_id), marking)

    assert marked.status is HomeworkStatus.MARKED
    filed: dict[str, Any] = marked.marking or {}
    assert filed["total_awarded"] == 4
    assert filed["total_available"] == 6
    assert filed["questions"][1]["comment"] == "No units."
