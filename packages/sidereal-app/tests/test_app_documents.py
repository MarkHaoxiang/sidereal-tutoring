from __future__ import annotations

from pathlib import Path
from uuid import UUID

from conftest import StubFetcher
from fastapi.testclient import TestClient
from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus
from sidereal_ingest.base import IngestError

FIXTURES = Path(__file__).parent / "fixtures"


def only_document(fake_directus: FakeDirectus) -> dict[str, object]:
    rows = fake_directus.rows(Collection.DOCUMENTS)
    assert len(rows) == 1
    return rows[0]


def test_pasted_text_is_ready_as_soon_as_it_is_filed(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/documents",
        headers=auth,
        json={
            "student_id": str(student_id),
            "title": "Lesson 3 notes",
            "source": {"type": "text", "text": "Factorise x^2 - 5x + 6."},
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["kind"] == "upload"
    assert body["title"] == "Lesson 3 notes"
    assert body["student"] == str(student_id)

    row = only_document(fake_directus)
    assert row["status"] == "ready"
    assert row["text"] == "Factorise x^2 - 5x + 6."
    assert row["error"] is None


def test_pasted_text_with_no_title_is_named_for_the_day_it_arrived(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/documents", headers=auth, json={"source": {"type": "text", "text": "Notes."}}
    )

    assert response.json()["title"].startswith("Pasted text ")
    assert only_document(fake_directus)["status"] == "ready"


def test_a_transcript_file_is_downloaded_and_read(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    file_id = fake_directus.register_file("lesson-3.vtt", (FIXTURES / "lesson-3.vtt").read_bytes())

    response = client.post(
        "/api/documents",
        headers=auth,
        json={"student_id": str(student_id), "source": {"type": "file", "file_id": file_id}},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "transcript"
    assert body["title"] == "lesson-3"
    assert body["file"] == file_id

    row = only_document(fake_directus)
    assert row["status"] == "ready"
    assert row["text"] == "We looked at indices."


def test_an_uploaded_worksheet_is_filed_as_an_upload(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    file_id = fake_directus.register_file("worksheet.txt", b"Solve for x.")

    response = client.post(
        "/api/documents", headers=auth, json={"source": {"type": "file", "file_id": file_id}}
    )

    assert response.json()["kind"] == "upload"
    row = only_document(fake_directus)
    assert row["status"] == "ready"
    assert row["text"] == "Solve for x."


def test_a_file_type_we_cannot_read_fails_with_the_types_we_can(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    file_id = fake_directus.register_file("marks.xlsx", b"PK\x03\x04")

    response = client.post(
        "/api/documents", headers=auth, json={"source": {"type": "file", "file_id": file_id}}
    )

    assert response.status_code == 202
    row = only_document(fake_directus)
    assert row["status"] == "failed"
    assert isinstance(row["error"], str)
    assert row["error"].startswith("marks.xlsx cannot be read.")


def test_a_link_is_read_and_titled_from_the_page(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/documents",
        headers=auth,
        json={"source": {"type": "url", "url": "https://example.test/indices"}},
    )

    assert response.status_code == 202
    assert response.json()["kind"] == "web_page"
    assert response.json()["title"] == "example.test"

    row = only_document(fake_directus)
    assert row["status"] == "ready"
    assert row["title"] == "Indices"
    assert row["text"] == "Powers of ten."


def test_a_link_that_cannot_be_read_fails_in_plain_english(
    client: TestClient, fake_directus: FakeDirectus, fetcher: StubFetcher, auth: dict[str, str]
) -> None:
    fetcher.error = IngestError("https://example.test/gone: 404", status=404)

    response = client.post(
        "/api/documents",
        headers=auth,
        json={"source": {"type": "url", "url": "https://example.test/gone"}},
    )

    assert response.status_code == 202
    row = only_document(fake_directus)
    assert row["status"] == "failed"
    assert row["error"] == "The link could not be fetched (HTTP 404)."


def test_retrying_a_failed_row_reads_it_again(
    client: TestClient, fake_directus: FakeDirectus, fetcher: StubFetcher, auth: dict[str, str]
) -> None:
    fetcher.error = IngestError("https://example.test/indices: 503", status=503)
    created = client.post(
        "/api/documents",
        headers=auth,
        json={"source": {"type": "url", "url": "https://example.test/indices"}},
    ).json()
    assert only_document(fake_directus)["status"] == "failed"
    fetcher.error = None

    response = client.post(f"/api/documents/{created['id']}/process", headers=auth)

    assert response.status_code == 202
    assert response.json()["id"] == created["id"]
    row = only_document(fake_directus)
    assert row["status"] == "ready"
    assert row["error"] is None
    assert row["title"] == "Indices"


def test_retrying_a_document_that_does_not_exist_is_directus_saying_so(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/documents/66666666-6666-4666-8666-666666666666/process", headers=auth
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "directus_rejected"


def test_a_source_with_no_type_is_rejected(client: TestClient, auth: dict[str, str]) -> None:
    response = client.post("/api/documents", headers=auth, json={"source": {"text": "Notes."}})

    assert response.status_code == 422
    # Every error body has a `detail`: an object for ours, FastAPI's list for a 422.
    assert isinstance(response.json()["detail"], list)


def test_a_link_that_is_not_http_is_rejected(client: TestClient, auth: dict[str, str]) -> None:
    response = client.post(
        "/api/documents",
        headers=auth,
        json={"source": {"type": "url", "url": "file:///etc/passwd"}},
    )

    assert response.status_code == 422


def test_an_unknown_body_field_is_rejected(client: TestClient, auth: dict[str, str]) -> None:
    response = client.post(
        "/api/documents",
        headers=auth,
        json={"source": {"type": "text", "text": "Notes."}, "kind": "transcript"},
    )

    assert response.status_code == 422


def test_filing_material_needs_a_token(client: TestClient) -> None:
    response = client.post("/api/documents", json={"source": {"type": "text", "text": "Notes."}})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_token"
