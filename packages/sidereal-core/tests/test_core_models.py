from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError
from sidereal_core.models import (
    GenerationJobDraft,
    GenerationKind,
    Student,
    StudentDraft,
    StudentStatus,
)

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_draft_payload_omits_unset_optionals_and_is_json_ready() -> None:
    student = StudentDraft(name="A. Tutee", level="GCSE", subjects=["maths"])
    job = GenerationJobDraft(
        kind=GenerationKind.HOMEWORK, student=STUDENT_ID, input={"documents": []}
    )

    assert student.payload() == {
        "name": "A. Tutee",
        "level": "GCSE",
        "subjects": ["maths"],
        "status": "active",
    }
    assert job.payload() == {
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


def test_a_student_with_no_subjects_reads_back_as_an_empty_list() -> None:
    student = Student.model_validate({"id": STUDENT_ID, "name": "A. Tutee", "subjects": None})

    assert student.subjects == []
