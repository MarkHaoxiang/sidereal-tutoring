"""An in-memory stand-in for Directus, so no test in this workspace needs a server."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

from sidereal_core.directus import DirectusClient

BASE_URL = "http://directus.test"
# Directus's own collections answer outside `/items`; the rows are stored the same way.
SYSTEM_ROUTES = {"users": "directus_users", "roles": "directus_roles"}
DEFAULT_TOKEN = "tutor-token"  # noqa: S105 - a test double's token, not a credential.
DEFAULT_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class FakeDirectus:
    """Items, `/users` and `/roles` CRUD over `httpx.MockTransport`.

    Filters understand one shape — `{"field": {"_eq": value}}` — which is all the
    workspace asks of Directus.
    """

    def __init__(self, *, token: str | None = DEFAULT_TOKEN, user: dict[str, Any] | None = None):
        self.token = token
        self.user: dict[str, Any] = user or {
            "id": str(DEFAULT_USER_ID),
            "email": "tutor@example.test",
            "status": "active",
        }
        self.items: dict[str, dict[str, dict[str, Any]]] = {}
        self.files: dict[str, tuple[dict[str, Any], bytes]] = {}
        self.requests: list[httpx.Request] = []
        self.unavailable = False
        self.unavailable_after: int | None = None

    def seed(self, collection: str, row: Mapping[str, Any]) -> dict[str, Any]:
        stored = {"id": str(uuid4()), **dict(row)}
        stored.setdefault("date_created", _now())
        self.items.setdefault(collection, {})[str(stored["id"])] = stored
        return stored

    def register_file(
        self,
        filename: str,
        content: bytes,
        *,
        file_id: str | None = None,
        media_type: str = "text/plain",
    ) -> str:
        """An uploaded asset: its `/files/{id}` row and the bytes `/assets/{id}` returns."""
        identifier = file_id or str(uuid4())
        self.files[identifier] = (
            {
                "id": identifier,
                "filename_download": filename,
                "filename_disk": f"{identifier}{Path(filename).suffix}",
                "title": Path(filename).stem,
                "type": media_type,
                "filesize": len(content),
            },
            content,
        )
        return identifier

    def rows(self, collection: str) -> list[dict[str, Any]]:
        return list(self.items.get(collection, {}).values())

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def client(self, token: str | None = DEFAULT_TOKEN) -> DirectusClient:
        return DirectusClient(BASE_URL, token, transport=self.transport())

    def _file(self, route: str, file_id: str) -> httpx.Response:
        stored = self.files.get(file_id)
        if stored is None:
            return _error(404, f"File {file_id} not found", "FORBIDDEN")
        row, content = stored
        if route == "files":
            return httpx.Response(200, json={"data": row})
        return _file_response(row["filename_download"], content, str(row["type"]))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.unavailable or (
            self.unavailable_after is not None and len(self.requests) > self.unavailable_after
        ):
            raise httpx.ConnectError("connection refused", request=request)
        if (
            self.token is not None
            and request.headers.get("authorization") != f"Bearer {self.token}"
        ):
            return _error(401, "Invalid user credentials.", "INVALID_CREDENTIALS")

        parts = request.url.path.strip("/").split("/")
        if parts == ["users", "me"]:
            return httpx.Response(200, json={"data": self.user})
        if parts[0] in ("files", "assets") and len(parts) == 2:
            return self._file(parts[0], parts[1])
        if parts[0] in SYSTEM_ROUTES and len(parts) in (1, 2):
            parts = ["items", SYSTEM_ROUTES[parts[0]], *parts[1:]]
        if parts[0] != "items" or len(parts) not in (2, 3):
            return _error(404, f"Route {request.url.path} does not exist.", "ROUTE_NOT_FOUND")

        collection = parts[1]
        rows = self.items.setdefault(collection, {})
        if len(parts) == 2:
            if request.method == "GET":
                return httpx.Response(200, json={"data": _query(list(rows.values()), request.url)})
            if request.method == "POST":
                return httpx.Response(200, json={"data": self.seed(collection, _payload(request))})
            return _error(405, f"{request.method} not allowed", "METHOD_NOT_ALLOWED")

        row = rows.get(parts[2])
        if row is None:
            return _error(404, f"{collection}/{parts[2]} not found", "RECORD_NOT_UNIQUE")
        if request.method == "GET":
            return httpx.Response(200, json={"data": row})
        if request.method == "PATCH":
            row.update(_payload(request))
            row["date_updated"] = _now()
            return httpx.Response(200, json={"data": row})
        if request.method == "DELETE":
            del rows[parts[2]]
            return httpx.Response(204)
        return _error(405, f"{request.method} not allowed", "METHOD_NOT_ALLOWED")


def _file_response(name: str, content: bytes, media_type: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=content,
        headers={
            "Content-Type": media_type,
            "Content-Disposition": f'attachment; filename="{name}"',
        },
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _payload(request: httpx.Request) -> dict[str, Any]:
    body = json.loads(request.content or b"{}")
    if not isinstance(body, dict):
        return {}
    return body


def _query(rows: list[dict[str, Any]], url: httpx.URL) -> list[dict[str, Any]]:
    raw = url.params.get("filter")
    if raw:
        for field, condition in json.loads(raw).items():
            if isinstance(condition, dict) and "_eq" in condition:
                rows = [row for row in rows if row.get(field) == condition["_eq"]]
    limit = url.params.get("limit")
    return rows[: int(limit)] if limit else rows


def _error(status: int, message: str, code: str) -> httpx.Response:
    return httpx.Response(
        status, json={"errors": [{"message": message, "extensions": {"code": code}}]}
    )
