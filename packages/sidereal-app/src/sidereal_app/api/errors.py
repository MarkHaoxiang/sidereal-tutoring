from __future__ import annotations

from typing import Any

DIRECTUS_UNAVAILABLE = "directus_unavailable"
BAD_CREDENTIALS = "invalid_token"
NO_CREDENTIALS = "missing_token"
DIRECTUS_REJECTED = "directus_rejected"


def detail(code: str, message: str) -> dict[str, Any]:
    """Every error body a client branches on. It reads the `code`, never the sentence."""
    return {"code": code, "message": message}
