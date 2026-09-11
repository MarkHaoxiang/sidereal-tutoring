from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError
from sidereal_core.models import (
    Document,
    DocumentKind,
    DocumentStatus,
    GenerationJobDraft,
    GenerationKind,
    JobStatus,
    Student,
    StudentDraft,
    StudentStatus,
)

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_draft_payload_omits_unset_optionals() -> None:
    draft = StudentDraft(name="A. Tutee", level="GCSE", subjects=["maths"])

    assert draft.payload() == {
        "name": "A. Tutee",
        "level": "GCSE",
        "subjects": ["maths"],
        "status": "active",
    }


def test_draft_payload_is_json_ready() -> None:
    draft = GenerationJobDraft(
        kind=GenerationKind.HOMEWORK, student=STUDENT_ID, input={"documents": []}
    )

    assert draft.payload() == {
        "kind": "homework",
        "student": str(STUDENT_ID),
        "status": "queued",
        "input": {"documents": []},
    }


def test_record_ignores_fields_directus_adds() -> None:
    student = Student.model_validate(
        {
            "id": str(STUDENT_ID),
            "name": "A. Tutee",
            "status": "paused",
            "date_created": "2026-01-02T03:04:05Z",
            "sort": 3,
        }
    )

    assert student.status is StudentStatus.PAUSED
    assert student.date_created is not None
    assert not hasattr(student, "sort")


def test_records_are_frozen() -> None:
    student = Student(id=STUDENT_ID, name="A. Tutee")

    with pytest.raises(ValidationError):
        student.name = "B. Tutee"


def test_document_defaults_to_pending() -> None:
    document = Document(id=STUDENT_ID, title="Lesson 1", kind=DocumentKind.TRANSCRIPT)

    assert document.status is DocumentStatus.PENDING
    assert document.metadata == {}


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Student.model_validate({"id": str(STUDENT_ID), "name": "A", "status": "retired"})


def test_job_status_values_are_the_wire_tokens() -> None:
    assert [status.value for status in JobStatus] == [
        "queued",
        "running",
        "succeeded",
        "failed",
    ]
