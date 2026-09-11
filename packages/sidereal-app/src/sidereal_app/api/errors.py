from __future__ import annotations

from typing import Any

DIRECTUS_UNAVAILABLE = "directus_unavailable"
BAD_CREDENTIALS = "invalid_token"
NO_CREDENTIALS = "missing_token"
DIRECTUS_REJECTED = "directus_rejected"
LOGIN_EXISTS = "login_exists"
LOGIN_MISSING = "login_missing"
INVALID_EMAIL = "invalid_email"
WEAK_PASSWORD = "weak_password"  # noqa: S105 - an error code, not a password.
STUDENT_ROLE_MISSING = "student_role_missing"
LOGIN_REFUSED = "login_refused"
LOGIN_FAILED = "login_failed"


def detail(code: str, message: str) -> dict[str, Any]:
    """What a client branches on. It reads the `code`, never the sentence."""
    return {"code": code, "message": message}


def error_body(code: str, message: str) -> dict[str, Any]:
    """The whole body, for a handler answering without `HTTPException` to wrap it."""
    return {"detail": detail(code, message)}
