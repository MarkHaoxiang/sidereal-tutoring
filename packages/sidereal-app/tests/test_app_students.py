from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus


def with_login(fake_directus: FakeDirectus, student_id: UUID) -> str:
    login = fake_directus.seed(
        Collection.DIRECTUS_USERS, {"email": "leo@sidereal.example.com", "status": "active"}
    )
    fake_directus.items[Collection.STUDENTS][str(student_id)]["user"] = login["id"]
    return str(login["id"])


def login_status(fake_directus: FakeDirectus, user_id: str) -> str:
    return str(fake_directus.items[Collection.DIRECTUS_USERS][user_id]["status"])


def test_archiving_suspends_the_login_and_unarchiving_brings_it_back(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    user_id = with_login(fake_directus, student_id)

    archived = client.post(f"/api/students/{student_id}/archive", headers=auth)

    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert login_status(fake_directus, user_id) == "suspended"

    active = client.post(f"/api/students/{student_id}/unarchive", headers=auth)

    assert active.json()["status"] == "active"
    assert login_status(fake_directus, user_id) == "active"


def test_deleting_a_student_takes_the_login_and_hands_their_uploads_over(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    user_id = with_login(fake_directus, student_id)
    fake_directus.register_file("working.jpg", b"jpeg", uploaded_by=user_id)

    response = client.delete(f"/api/students/{student_id}", headers=auth)

    assert response.status_code == 204
    assert not fake_directus.rows(Collection.STUDENTS)
    assert user_id not in fake_directus.items[Collection.DIRECTUS_USERS]
    uploaders = [row["uploaded_by"] for row, _ in fake_directus.files.values()]
    assert uploaders == [str(DEFAULT_USER_ID)]


def test_a_student_the_caller_cannot_see_is_not_theirs_to_delete(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.delete(f"/api/students/{UUID(int=7)}", headers=auth)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "student_not_found"


def test_a_student_may_not_archive_or_delete_anyone(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    fake_directus.items[Collection.STUDENTS][str(student_id)]["user"] = str(DEFAULT_USER_ID)

    for response in (
        client.post(f"/api/students/{student_id}/archive", headers=auth),
        client.delete(f"/api/students/{student_id}", headers=auth),
    ):
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "tutor_only"
