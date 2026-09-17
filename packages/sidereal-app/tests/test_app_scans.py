from __future__ import annotations

import io
from collections.abc import Iterator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sidereal_app.deps import get_http_client, get_scanner
from sidereal_app.main import create_app
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus
from sidereal_ingest.scan import ScanIngester
from sidereal_ingest.transcribe import Confidence, FakeTranscriber, Transcription

WORKING = Transcription(text="$x = 4$", confidence=Confidence.HIGH, questions=())


class StudentsOwnDirectus(FakeDirectus):
    """A Directus whose rules let a student write their own submission fields and no others."""

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and b"generated_from" in (request.content or b""):
            return httpx.Response(
                403,
                json={"errors": [{"message": "no", "extensions": {"code": "FORBIDDEN"}}]},
            )
        return super().handle(request)


@pytest.fixture
def student_directus() -> StudentsOwnDirectus:
    return StudentsOwnDirectus()


@pytest.fixture
def student_client(
    student_directus: StudentsOwnDirectus, scanner: ScanIngester
) -> Iterator[TestClient]:
    app = create_app()
    pool = httpx.AsyncClient(transport=student_directus.transport())
    app.dependency_overrides[get_http_client] = lambda: pool
    app.dependency_overrides[get_scanner] = lambda: scanner
    with TestClient(app) as test_client:
        yield test_client


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def scan_file(fake_directus: FakeDirectus, name: str = "page-1.png") -> str:
    return fake_directus.register_file(name, png(), media_type="image/png")


def seed_homework(fake_directus: FakeDirectus, student_id: UUID, *, file_id: str) -> str:
    row = fake_directus.seed(
        Collection.HOMEWORK,
        {
            "student": str(student_id),
            "title": "Week 3",
            "content": "## Week 3",
            "submission_file": file_id,
        },
    )
    return str(row["id"])


def test_a_scan_is_filed_pending_with_its_pages_then_transcribed(
    client: TestClient,
    fake_directus: FakeDirectus,
    transcriber: FakeTranscriber,
    auth: dict[str, str],
) -> None:
    first = scan_file(fake_directus, "page-1.png")
    second = scan_file(fake_directus, "page-2.png")

    response = client.post(
        "/api/documents",
        headers=auth,
        json={"title": "Week 3 working", "source": {"type": "scan", "file_ids": [first, second]}},
    )

    assert response.status_code == 202
    assert response.json()["kind"] == "scan"
    assert response.json()["status"] == "pending"
    assert [
        (row["file"], row["sort"]) for row in fake_directus.rows(Collection.DOCUMENT_PAGES)
    ] == [
        (first, 1),
        (second, 2),
    ]
    row = fake_directus.rows(Collection.DOCUMENTS)[0]
    assert row["status"] == "ready"
    assert row.get("transcription") is None
    assert len(transcriber.pages) == 2


def test_a_scan_of_solutions_carries_the_paper_it_answers(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    paper = fake_directus.seed(
        Collection.PAPERS,
        {"title": "Pure 1", "structure": {"title": "Pure 1", "questions": [{"number": "1"}]}},
    )

    response = client.post(
        "/api/documents",
        headers=auth,
        json={
            "source": {
                "type": "scan",
                "file_ids": [scan_file(fake_directus)],
                "paper_id": str(paper["id"]),
            }
        },
    )

    assert response.status_code == 202
    assert response.json()["paper"] == str(paper["id"])
    row = fake_directus.rows(Collection.DOCUMENTS)[0]
    assert row["status"] == "ready"
    questions = row["transcription"]["questions"]
    assert [question["number"] for question in questions] == ["1"]
    assert questions[0]["confidence"] == "low"


def test_a_scan_needs_at_least_one_page(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/documents", headers=auth, json={"source": {"type": "scan", "file_ids": []}}
    )

    assert response.status_code == 422
    assert fake_directus.rows(Collection.DOCUMENTS) == []


def test_a_tutor_transcribes_a_students_hand_in(
    client: TestClient,
    fake_directus: FakeDirectus,
    student_id: UUID,
    transcriber: FakeTranscriber,
    auth: dict[str, str],
) -> None:
    transcriber.transcription = WORKING
    homework_id = seed_homework(fake_directus, student_id, file_id=scan_file(fake_directus))

    response = client.post(f"/api/homework/{homework_id}/transcribe", headers=auth)

    assert response.status_code == 200
    assert response.json()["submission_transcription"]["text"] == "$x = 4$"
    assert response.json()["submission_transcription"]["confidence"] == "high"


def test_the_student_who_owns_the_homework_may_transcribe_it(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    student = fake_directus.seed(
        Collection.STUDENTS, {"name": "A. Tutee", "user": str(DEFAULT_USER_ID)}
    )
    homework_id = seed_homework(
        fake_directus, UUID(str(student["id"])), file_id=scan_file(fake_directus)
    )

    response = client.post(f"/api/homework/{homework_id}/transcribe", headers=auth)

    assert response.status_code == 200
    assert response.json()["submission_transcription"]["questions"] == []


def test_a_student_who_may_write_no_other_field_still_transcribes_their_own_hand_in(
    student_client: TestClient,
    student_directus: StudentsOwnDirectus,
    transcriber: FakeTranscriber,
    auth: dict[str, str],
) -> None:
    transcriber.transcription = WORKING
    student = student_directus.seed(
        Collection.STUDENTS, {"name": "A. Tutee", "user": str(DEFAULT_USER_ID)}
    )
    homework_id = seed_homework(
        student_directus, UUID(str(student["id"])), file_id=scan_file(student_directus)
    )

    response = student_client.post(f"/api/homework/{homework_id}/transcribe", headers=auth)

    assert response.status_code == 200
    assert response.json()["submission_transcription"]["text"] == "$x = 4$"
    assert response.json()["submission_transcription"]["model"] == "fake"


def test_a_student_cannot_transcribe_another_students_hand_in(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    fake_directus.seed(Collection.STUDENTS, {"name": "A. Tutee", "user": str(DEFAULT_USER_ID)})
    homework_id = seed_homework(fake_directus, uuid4(), file_id=scan_file(fake_directus))

    response = client.post(f"/api/homework/{homework_id}/transcribe", headers=auth)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "tutor_only"


def test_a_homework_with_nothing_handed_in_is_a_sentence_not_a_crash(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    row = fake_directus.seed(
        Collection.HOMEWORK,
        {"student": str(student_id), "title": "Week 3", "content": "## Week 3"},
    )

    response = client.post(f"/api/homework/{row['id']}/transcribe", headers=auth)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "material_unusable"
    assert "handed in" in response.json()["detail"]["message"]
