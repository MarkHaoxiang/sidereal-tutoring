from __future__ import annotations

from datetime import date
from uuid import UUID

from sidereal_core.models import (
    Document,
    DocumentKind,
    Homework,
    HomeworkStatus,
    Question,
    Student,
)
from sidereal_generate.models import GenerationRequest, MarkedHomework
from sidereal_generate.prompts import render
from sidereal_generate.settings import DEFAULT_MODEL, generate_settings

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
HOMEWORK_ID = UUID("33333333-3333-4333-8333-333333333333")
QUESTION_ID = UUID("44444444-4444-4444-8444-444444444444")


def test_render_states_what_is_unknown_rather_than_omitting_it() -> None:
    rendered = render(GenerationRequest(student=Student(id=STUDENT_ID, name="A. Tutee")))

    assert "name: A. Tutee" in rendered
    assert "level: unstated" in rendered
    assert "notes: none" in rendered
    assert "<document" not in rendered


def test_render_includes_period_documents_and_instructions() -> None:
    rendered = render(
        GenerationRequest(
            student=Student(id=STUDENT_ID, name="A. Tutee", subjects=["maths", "physics"]),
            documents=(
                Document(
                    id=DOCUMENT_ID, title="Lesson 3", kind=DocumentKind.TRANSCRIPT, text="Body."
                ),
            ),
            instructions="Keep it short.",
            period_start=date(2026, 1, 5),
            period_end=date(2026, 2, 16),
        )
    )

    assert "subjects: maths, physics" in rendered
    assert "<period>2026-01-05 (Monday) to 2026-02-16 (Monday)</period>" in rendered
    assert "<instructions>Keep it short.</instructions>" in rendered
    assert f'<document id="{DOCUMENT_ID}" kind="transcript" title="Lesson 3">' in rendered
    assert "Body." in rendered


def test_settings_default_and_override() -> None:
    assert generate_settings({}).model == DEFAULT_MODEL
    assert generate_settings({"SIDEREAL_GENERATE_MODEL": "claude-opus-5"}).model == "claude-opus-5"
    assert generate_settings({"SIDEREAL_GENERATE_MAX_TOKENS": "123"}).max_tokens == 123


def test_render_gives_every_kind_today_and_the_next_lesson() -> None:
    rendered = render(
        GenerationRequest(
            student=Student(id=STUDENT_ID, name="A. Tutee"),
            today=date(2026, 9, 17),
            session_date=date(2026, 9, 18),
        )
    )

    assert "today: 2026-09-17 (Thursday)" in rendered
    assert "next lesson: 2026-09-18 (Friday)" in rendered


def test_render_says_there_is_no_next_lesson_rather_than_leaving_it_out() -> None:
    rendered = render(
        GenerationRequest(student=Student(id=STUDENT_ID, name="A. Tutee"), today=date(2026, 9, 17))
    )

    assert "next lesson: none" in rendered


def test_a_hand_in_carries_the_questions_the_answers_the_working_and_the_marks() -> None:
    rendered = render(
        GenerationRequest(
            student=Student(id=STUDENT_ID, name="A. Tutee"),
            homework=(
                MarkedHomework(
                    homework=Homework(
                        id=HOMEWORK_ID,
                        student=STUDENT_ID,
                        title="Moments",
                        content="",
                        status=HomeworkStatus.MARKED,
                        due_on=date(2026, 9, 24),
                        submission="Q1 R_D = 90 N",
                        submission_transcription={
                            "text": "Total moment = 4.8 + 2.4",
                            "confidence": "high",
                        },
                        marking={
                            "total_awarded": 4,
                            "total_available": 6,
                            "questions": [
                                {
                                    "number": "1",
                                    "marks_awarded": 3,
                                    "marks_available": 3,
                                    "comment": "Clean.",
                                }
                            ],
                            "comment": "Name the pivot.",
                        },
                    ),
                    questions=(
                        Question(
                            id=QUESTION_ID,
                            text="A uniform plank $A B$ has length $4.0$ m.",
                            number="1",
                            marks=3,
                        ),
                    ),
                ),
            ),
        )
    )

    assert '<homework title="Moments" status="marked" due="2026-09-24 (Thursday)">' in rendered
    assert '<question number="1" marks="3">A uniform plank AB has length 4.0 m.</question>' in (
        rendered
    )
    assert "<submission>Q1 R_D = 90 N</submission>" in rendered
    assert '<working read="high">Total moment = 4.8 + 2.4</working>' in rendered
    assert '<marking total="4 out of 6">' in rendered
    assert "<comment>Name the pivot.</comment>" in rendered


def test_a_hand_in_with_nothing_on_it_says_so_rather_than_going_quiet() -> None:
    """Silence is what let feedback praise working that was never handed in."""
    rendered = render(
        GenerationRequest(
            student=Student(id=STUDENT_ID, name="A. Tutee"),
            homework=(
                MarkedHomework(
                    homework=Homework(
                        id=HOMEWORK_ID, student=STUDENT_ID, title="Moments", content=""
                    )
                ),
            ),
        )
    )

    assert "<submission>nothing was typed in</submission>" in rendered
    assert "<working>no photograph of working was handed in</working>" in rendered
    assert "<marking>the tutor has not marked this yet</marking>" in rendered
