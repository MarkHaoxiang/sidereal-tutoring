from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus

EMAIL = "tutee@sidereal.example.com"
PASSWORD = "correct-horse"


@pytest.fixture
def student_role(fake_directus: FakeDirectus) -> dict[str, Any]:
    return fake_directus.seed(Collection.DIRECTUS_ROLES, {"name": "Student"})


def login(client: TestClient, student_id: UUID, auth: dict[str, str], **body: str) -> Any:
    return client.post(
        f"/api/students/{student_id}/login",
        headers=auth,
        json={"email": EMAIL, "password": PASSWORD, **body},
    )


def student(fake_directus: FakeDirectus, student_id: UUID) -> dict[str, Any]:
    return fake_directus.items[Collection.STUDENTS][str(student_id)]


def test_me_is_a_tutor_when_no_student_row_points_at_the_caller(
    client: TestClient, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.get("/api/me", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(DEFAULT_USER_ID)
    assert body["role"] == "tutor"
    assert body["student_id"] is None
    assert body["email"] == "tutor@example.test"


def test_me_is_a_tutor_when_some_other_student_has_a_login(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    fake_directus.seed(Collection.STUDENTS, {"name": "B. Tutee", "user": str(uuid4())})

    assert client.get("/api/me", headers=auth).json()["role"] == "tutor"


def test_me_is_a_student_when_a_student_row_points_at_the_caller(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    student(fake_directus, student_id)["user"] = str(DEFAULT_USER_ID)

    body = client.get("/api/me", headers=auth).json()

    assert body["role"] == "student"
    assert body["student_id"] == str(student_id)


def test_me_needs_a_token(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401


def test_creating_a_login_returns_201_and_links_the_student(
    client: TestClient,
    fake_directus: FakeDirectus,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    response = login(client, student_id, auth)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == EMAIL
    user = fake_directus.rows(Collection.DIRECTUS_USERS)[0]
    assert user["id"] == body["user_id"]
    assert user["role"] == student_role["id"]
    assert user["first_name"] == "A. Tutee"
    assert student(fake_directus, student_id)["user"] == body["user_id"]


def test_a_second_login_is_409(
    client: TestClient,
    fake_directus: FakeDirectus,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    login(client, student_id, auth)

    response = login(client, student_id, auth, email="other@sidereal.example.com")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "login_exists"
    assert response.json()["detail"]["message"] == "This student already has a login."
    assert len(fake_directus.rows(Collection.DIRECTUS_USERS)) == 1


def test_a_short_password_is_422_with_a_plain_message(
    client: TestClient,
    fake_directus: FakeDirectus,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    response = login(client, student_id, auth, password="short")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "weak_password"
    assert response.json()["detail"]["message"] == "A password needs at least 8 characters."
    assert fake_directus.rows(Collection.DIRECTUS_USERS) == []


def test_a_bad_email_is_422(
    client: TestClient, student_id: UUID, auth: dict[str, str], student_role: dict[str, Any]
) -> None:
    response = login(client, student_id, auth, email="nobody")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_email"


def test_a_login_for_an_unknown_student_is_404_in_plain_words(
    client: TestClient, auth: dict[str, str], student_role: dict[str, Any]
) -> None:
    response = login(client, uuid4(), auth)

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "login_refused",
        "message": "That student could not be found.",
    }


def test_without_a_student_role_creating_a_login_is_500(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    response = login(client, student_id, auth)

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "student_role_missing"
    assert fake_directus.rows(Collection.DIRECTUS_USERS) == []


def test_resetting_the_password_is_204(
    client: TestClient,
    fake_directus: FakeDirectus,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    login(client, student_id, auth)

    response = client.post(
        f"/api/students/{student_id}/login/password",
        headers=auth,
        json={"password": "a-longer-one"},
    )

    assert response.status_code == 204
    assert not response.content
    assert fake_directus.rows(Collection.DIRECTUS_USERS)[0]["password"] == "a-longer-one"


def test_resetting_a_password_without_a_login_is_404(
    client: TestClient, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/students/{student_id}/login/password", headers=auth, json={"password": PASSWORD}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "login_missing"


def test_resetting_to_a_short_password_is_422(
    client: TestClient,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    login(client, student_id, auth)

    response = client.post(
        f"/api/students/{student_id}/login/password", headers=auth, json={"password": "short"}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "weak_password"


def test_removing_a_login_is_204_and_keeps_the_student(
    client: TestClient,
    fake_directus: FakeDirectus,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    login(client, student_id, auth)

    response = client.delete(f"/api/students/{student_id}/login", headers=auth)

    assert response.status_code == 204
    assert not response.content
    assert fake_directus.rows(Collection.DIRECTUS_USERS) == []
    assert student(fake_directus, student_id)["user"] is None
    assert student(fake_directus, student_id)["name"] == "A. Tutee"


def test_removing_a_login_that_is_not_there_is_404(
    client: TestClient, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.delete(f"/api/students/{student_id}/login", headers=auth)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "login_missing"


def test_a_login_can_be_set_up_again_after_removal(
    client: TestClient,
    student_id: UUID,
    auth: dict[str, str],
    student_role: dict[str, Any],
) -> None:
    login(client, student_id, auth)
    client.delete(f"/api/students/{student_id}/login", headers=auth)

    assert login(client, student_id, auth).status_code == 201
