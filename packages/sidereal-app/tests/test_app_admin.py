from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sidereal_core.models import Collection, GenerationKind, JobStatus
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus
from sidereal_core.tutors import TUTOR_ROLE

PASSWORD = "correct-horse"
EMAIL = "tutor@sidereal.example.com"
SOMEONE = uuid4()
ADMIN_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/admin/health", None),
    ("GET", "/api/admin/tutors", None),
    ("POST", "/api/admin/tutors", {"email": EMAIL, "password": PASSWORD}),
    ("POST", f"/api/admin/tutors/{SOMEONE}/password", {"password": PASSWORD}),
    ("PATCH", f"/api/admin/tutors/{SOMEONE}", {"status": "suspended"}),
    ("DELETE", f"/api/admin/tutors/{SOMEONE}", None),
    ("GET", "/api/admin/jobs", None),
]


@pytest.fixture
def admin(fake_directus: FakeDirectus) -> FakeDirectus:
    fake_directus.admin = True
    fake_directus.seed(Collection.DIRECTUS_ROLES, {"name": TUTOR_ROLE})
    return fake_directus


def tutor_role(fake: FakeDirectus) -> str:
    return str(fake.rows(Collection.DIRECTUS_ROLES)[0]["id"])


def seed_tutor(fake: FakeDirectus, email: str = EMAIL) -> UUID:
    row = fake.seed(
        Collection.DIRECTUS_USERS,
        {"email": email, "role": tutor_role(fake), "status": "active"},
    )
    return UUID(str(row["id"]))


def call(client: TestClient, method: str, path: str, auth: dict[str, str], body: Any) -> Any:
    return client.request(method, path, headers=auth, json=body)


def test_me_says_admin_for_a_caller_whose_policy_grants_admin_access(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    body = client.get("/api/me", headers=auth).json()

    assert body["role"] == "admin"
    assert body["student_id"] is None


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ROUTES)
def test_a_tutor_is_refused_every_admin_route(
    client: TestClient,
    admin: FakeDirectus,
    auth: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    admin.admin = False

    response = call(client, method, path, auth, body)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_only"


def test_a_student_is_refused_an_admin_route(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str], student_id: UUID
) -> None:
    """`require_admin` is one dependency: the sweep above is what guards every route."""
    admin.admin = False
    admin.items[Collection.STUDENTS][str(student_id)]["user"] = str(DEFAULT_USER_ID)

    response = client.get("/api/admin/tutors", headers=auth)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_only"


def test_health_names_every_service_and_the_counts(
    client: TestClient,
    admin: FakeDirectus,
    auth: dict[str, str],
    student_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_BACKEND", "fake")
    monkeypatch.setenv("SIDEREAL_GENERATE_MODEL", "a-model")
    seed_tutor(admin)

    body = client.get("/api/admin/health", headers=auth).json()

    assert body["directus"]["ok"] is True
    assert body["directus"]["license"]["status"] == "active"
    assert body["api"]["ok"] is True
    assert body["typeset"]["ok"] is True
    assert body["generation"] == {"backend": "fake", "model": "a-model"}
    assert body["counts"]["tutors"] == 1
    assert body["counts"]["students"] == 1


def test_directus_being_down_is_a_degraded_health_not_a_503(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    # `/users/me` and `/policies/me/globals` answer; everything the health probes ask does not.
    admin.unavailable_after = 2

    response = client.get("/api/admin/health", headers=auth)

    assert response.status_code == 200
    assert response.json()["directus"]["ok"] is False


def test_a_tutor_is_created_listed_and_counted(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    created = client.post(
        "/api/admin/tutors",
        headers=auth,
        json={"email": EMAIL, "password": PASSWORD, "first_name": "T"},
    )

    assert created.status_code == 201
    listed = client.get("/api/admin/tutors", headers=auth).json()
    assert [(row["email"], row["students"]) for row in listed] == [(EMAIL, 0)]
    assert listed[0]["user_id"] == created.json()["user_id"]


def test_a_weak_password_is_refused_before_directus_sees_it(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/admin/tutors", headers=auth, json={"email": EMAIL, "password": "short"}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "weak_password"


def test_a_password_reset_answers_204(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    tutor = seed_tutor(admin)

    response = client.post(
        f"/api/admin/tutors/{tutor}/password", headers=auth, json={"password": "a-longer-secret"}
    )

    assert response.status_code == 204
    assert admin.items[Collection.DIRECTUS_USERS][str(tutor)]["password"] == "a-longer-secret"


def test_a_tutor_can_be_suspended_and_reactivated(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    tutor = seed_tutor(admin)

    suspended = client.patch(
        f"/api/admin/tutors/{tutor}", headers=auth, json={"status": "suspended"}
    )
    reactivated = client.patch(
        f"/api/admin/tutors/{tutor}", headers=auth, json={"status": "active"}
    )

    assert suspended.json()["status"] == "suspended"
    assert reactivated.json()["status"] == "active"


def test_a_tutor_who_still_has_students_is_a_409(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    tutor = seed_tutor(admin)
    student = admin.seed(Collection.STUDENTS, {"name": "Theirs", "tutor": str(tutor)})

    refused = client.delete(f"/api/admin/tutors/{tutor}", headers=auth)

    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "tutor_has_students"
    assert "Reassign" in refused.json()["detail"]["message"]

    student["tutor"] = None
    assert client.delete(f"/api/admin/tutors/{tutor}", headers=auth).status_code == 204


def test_an_unknown_tutor_is_a_404(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    response = client.delete(f"/api/admin/tutors/{uuid4()}", headers=auth)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "tutor_not_found"


def test_jobs_list_across_tutors_with_the_student_and_their_tutor(
    client: TestClient, admin: FakeDirectus, auth: dict[str, str]
) -> None:
    tutor = seed_tutor(admin)
    theirs = admin.seed(Collection.STUDENTS, {"name": "Theirs", "tutor": str(tutor)})
    admin.seed(
        Collection.GENERATION_JOBS,
        {
            "kind": GenerationKind.HOMEWORK.value,
            "status": JobStatus.SUCCEEDED.value,
            "student": str(theirs["id"]),
        },
    )
    admin.seed(
        Collection.GENERATION_JOBS,
        {"kind": GenerationKind.PLAN.value, "status": JobStatus.FAILED.value},
    )

    rows = client.get("/api/admin/jobs", headers=auth).json()
    succeeded = client.get("/api/admin/jobs?status=succeeded", headers=auth).json()

    assert len(rows) == 2
    assert succeeded == [
        {
            "job": succeeded[0]["job"],
            "student_name": "Theirs",
            "tutor_email": EMAIL,
        }
    ]
    assert succeeded[0]["job"]["kind"] == "homework"
