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
TYPESET_UNAVAILABLE = "typeset_unavailable"
TYPESET_FAILED = "typeset_failed"
TYPESET_TOO_LARGE = "typeset_too_large"
ASSET_UNREADABLE = "asset_unreadable"
STUDENT_NOT_FOUND = "student_not_found"
TUTOR_ONLY = "tutor_only"
ADMIN_ONLY = "admin_only"
TUTOR_ROLE_MISSING = "tutor_role_missing"
TUTOR_NOT_FOUND = "tutor_not_found"
TUTOR_HAS_STUDENTS = "tutor_has_students"
TUTOR_REFUSED = "tutor_refused"
FORMAT_UNSUPPORTED = "format_unsupported"
PAGES_UNSUPPORTED = "pages_unsupported"
HOMEWORK_UNSUPPORTED = "homework_unsupported"
STUDENT_REQUIRED = "student_required"
STUDENT_GONE = "student_gone"
DOCUMENT_REQUIRED = "document_required"
PAPER_UNUSABLE = "paper_unusable"
MATERIAL_UNUSABLE = "material_unusable"
GENERATION_NOT_CONFIGURED = "generation_not_configured"
TOO_MANY_CHECKS = "too_many_checks"
SERVICE_TOKEN_MISSING = "service_token_missing"  # noqa: S105 - an error code, not a token.


def detail(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """What a client branches on. It reads the `code`, never the sentence."""
    return {"code": code, "message": message, **extra}


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """The whole body, for a handler answering without `HTTPException` to wrap it."""
    return {"detail": detail(code, message, **extra)}
