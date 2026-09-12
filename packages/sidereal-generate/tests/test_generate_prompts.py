from __future__ import annotations

from datetime import date
from uuid import UUID

from sidereal_core.models import Document, DocumentKind, Student
from sidereal_generate.models import GenerationRequest
from sidereal_generate.prompts import render
from sidereal_generate.settings import DEFAULT_MODEL, generate_settings

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


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
    assert "<period>2026-01-05 to 2026-02-16</period>" in rendered
    assert "<instructions>Keep it short.</instructions>" in rendered
    assert f'<document id="{DOCUMENT_ID}" kind="transcript" title="Lesson 3">' in rendered
    assert "Body." in rendered


def test_settings_default_and_override() -> None:
    assert generate_settings({}).model == DEFAULT_MODEL
    assert generate_settings({"SIDEREAL_GENERATE_MODEL": "claude-opus-5"}).model == "claude-opus-5"
    assert generate_settings({"SIDEREAL_GENERATE_MAX_TOKENS": "123"}).max_tokens == 123
