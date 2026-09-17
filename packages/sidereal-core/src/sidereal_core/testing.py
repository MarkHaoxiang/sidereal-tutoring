"""In-memory stand-ins for Directus and typeset, so no test in this workspace needs a server."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

from sidereal_core.directus import DirectusClient
from sidereal_core.typeset import TypesetClient

BASE_URL = "http://directus.test"
# Directus's own collections answer outside `/items`; the rows are stored the same way.
SYSTEM_ROUTES = {
    "users": "directus_users",
    "roles": "directus_roles",
    "folders": "directus_folders",
}
# Which collection a nested create on a relation field writes into.
RELATED = {"user": "directus_users"}
DEFAULT_TOKEN = "tutor-token"  # noqa: S105 - a test double's token, not a credential.
DEFAULT_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

FAKE_DIRECTUS_VERSION = "0.0.0-fake"
FAKE_LICENCE = {"name": "Fake Grant", "status": "active"}

TYPESET_URL = "http://typeset.test"
# Source carrying this never compiles, so a test can drive the retry and the failure path.
FAIL_MARKER = "#does-not-compile"
FAKE_PDF = b"%PDF-1.7\n%% sidereal FakeTypeset: not a compiled document\n%%EOF\n"
FAKE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 595 842"><title>page {page}</title></svg>'
)


class FakeDirectus:
    """Items, `/users`, `/roles` and `/folders` CRUD over `httpx.MockTransport`.

    Filters understand one shape — `{"field": {"_eq": value}}` — which is all the
    workspace asks of Directus.
    """

    def __init__(
        self,
        *,
        token: str | None = DEFAULT_TOKEN,
        user: dict[str, Any] | None = None,
        admin: bool = False,
    ):
        self.token = token
        self.user: dict[str, Any] = user or {
            "id": str(DEFAULT_USER_ID),
            "email": "tutor@example.test",
            "status": "active",
        }
        # `admin_access` is on no row: `/policies/me/globals` is where Directus answers it.
        self.admin = admin
        self.items: dict[str, dict[str, dict[str, Any]]] = {}
        self.files: dict[str, tuple[dict[str, Any], bytes]] = {}
        self.requests: list[httpx.Request] = []
        self.unavailable = False
        self.unavailable_after: int | None = None
        self.version = FAKE_DIRECTUS_VERSION
        self.licence: dict[str, Any] | None = dict(FAKE_LICENCE)

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
        uploaded_by: str | None = None,
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
                "uploaded_by": uploaded_by or str(self.user["id"]),
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

    def _upload(self, request: httpx.Request) -> httpx.Response:
        fields = _multipart(request)
        name, content, media_type = fields.get("file", ("upload.bin", b"", "text/plain"))
        file_id = self.register_file(name, content, media_type=media_type)
        row = self.files[file_id][0]
        for field in ("title", "folder"):
            if field in fields:
                row[field] = fields[field][1].decode()
        return httpx.Response(200, json={"data": row})

    def _nested(self, payload: dict[str, Any]) -> dict[str, Any]:
        """An object where a relation is expected creates that row, as Directus does."""
        written: dict[str, Any] = {}
        for field, value in payload.items():
            related = RELATED.get(field)
            if related is not None and isinstance(value, dict):
                written[field] = self.seed(related, value)["id"]
            else:
                written[field] = value
        return written

    def _expand(self, row: dict[str, Any], url: httpx.URL) -> dict[str, Any]:
        """`fields=x.id` answers with the related row's id nested under `x`, as Directus does."""
        expanded = dict(row)
        for field in (url.params.get("fields") or "").split(","):
            name, _, leaf = field.partition(".")
            if leaf and name in expanded:
                expanded[name] = {leaf: expanded[name]}
        return expanded

    def _file(self, route: str, file_id: str, request: httpx.Request) -> httpx.Response:
        stored = self.files.get(file_id)
        if stored is None:
            return _error(404, f"File {file_id} not found", "FORBIDDEN")
        row, content = stored
        if route == "assets":
            return _file_response(row["filename_download"], content, str(row["type"]))
        if request.method == "PATCH":
            row.update(_payload(request))
            return httpx.Response(200, json={"data": row})
        if request.method == "DELETE":
            del self.files[file_id]
            return httpx.Response(204)
        return httpx.Response(200, json={"data": row})

    def _uploader(self, user_id: str) -> bool:
        """Directus's own `directus_files_uploaded_by_foreign`, which no snapshot can loosen."""
        return any(row.get("uploaded_by") == user_id for row, _ in self.files.values())

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
        if parts == ["policies", "me", "globals"]:
            return httpx.Response(
                200,
                json={"data": {"app_access": True, "admin_access": self.admin}},
            )
        if parts == ["server", "info"]:
            return httpx.Response(200, json={"data": {"version": self.version}})
        if parts == ["license"]:
            if self.licence is None:
                return _error(403, "You don't have permission to access this.", "FORBIDDEN")
            return httpx.Response(200, json={"data": self.licence})
        if parts == ["files"] and request.method == "POST":
            return self._upload(request)
        if parts == ["files"] and request.method == "GET":
            listing = [row for row, _ in self.files.values()]
            return httpx.Response(200, json={"data": _query(listing, request.url)})
        if parts[0] in ("files", "assets") and len(parts) == 2:
            return self._file(parts[0], parts[1], request)
        if parts[0] in SYSTEM_ROUTES and len(parts) in (1, 2):
            parts = ["items", SYSTEM_ROUTES[parts[0]], *parts[1:]]
        if parts[0] != "items" or len(parts) not in (2, 3):
            return _error(404, f"Route {request.url.path} does not exist.", "ROUTE_NOT_FOUND")

        collection = parts[1]
        rows = self.items.setdefault(collection, {})
        if len(parts) == 2:
            if request.method == "GET":
                if request.url.params.get("aggregate[count]"):
                    return httpx.Response(
                        200, json={"data": _aggregate(list(rows.values()), request.url)}
                    )
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
            payload = self._nested(_payload(request))
            row.update(payload)
            row["date_updated"] = _now()
            return httpx.Response(200, json={"data": self._expand(row, request.url)})
        if request.method == "DELETE":
            if collection == "directus_users" and self._uploader(parts[2]):
                return _error(
                    500,
                    'update or delete on table "directus_users" violates foreign key constraint '
                    '"directus_files_uploaded_by_foreign" on table "directus_files"',
                    "INTERNAL_SERVER_ERROR",
                )
            del rows[parts[2]]
            return httpx.Response(204)
        return _error(405, f"{request.method} not allowed", "METHOD_NOT_ALLOWED")


class FakeTypeset:
    """The typeset service's contract over `httpx.MockTransport`. It compiles nothing.

    Source carrying `FAIL_MARKER` comes back as a 422 with diagnostics, which is how a
    test drives the retry and the persistent-failure path without a Typst compiler.
    """

    def __init__(self, *, pages: int = 1) -> None:
        self.pdf = FAKE_PDF
        self.pages = pages
        self.compiled: list[str] = []
        self.wrapped: list[dict[str, Any]] = []
        self.rendered: list[dict[str, Any]] = []
        self.unavailable = False

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def client(self) -> TypesetClient:
        return TypesetClient(TYPESET_URL, transport=self.transport())

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.unavailable:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        if path == "/healthz":
            return httpx.Response(200, text="ok")
        if path == "/template":
            return self._template(_payload(request))
        if path == "/compile":
            return self._compile(_payload(request))
        if path == "/render":
            return self._render(_payload(request))
        return httpx.Response(404, json={"message": f"no route {path}"})

    def _template(self, body: dict[str, Any]) -> httpx.Response:
        self.wrapped.append(body)
        due = body.get("due") or "no date"
        source = (
            f"// FakeTypeset wrapper: {body.get('kind')}\n"
            f"= {body.get('title')}\n"
            f"{body.get('student')} — due {due}\n\n"
            f"{body.get('body', '')}\n"
        )
        return httpx.Response(200, json={"source": source})

    def _render(self, body: dict[str, Any]) -> httpx.Response:
        """A canonical document, rendered by nobody. A `FAIL_MARKER` anywhere in it is the 422."""
        self.rendered.append(body)
        document = json.dumps(body.get("document", {}))
        if FAIL_MARKER in document or FAIL_MARKER in json.dumps(body.get("mark_scheme")):
            return httpx.Response(
                422,
                json={
                    "diagnostics": [
                        {"message": "unknown function `does-not-compile`", "line": 1, "column": 1}
                    ]
                },
            )
        source = f"// FakeTypeset render: {body.get('kind')}\n{document}\n"
        if body.get("output") == "source":
            return httpx.Response(200, json={"source": source})
        if body.get("output") == "svg":
            pages = [FAKE_SVG.format(page=n) for n in range(1, self.pages + 1)]
            return httpx.Response(200, json={"pages": pages})
        return httpx.Response(200, content=self.pdf, headers={"Content-Type": "application/pdf"})

    def _compile(self, body: dict[str, Any]) -> httpx.Response:
        source = str(body.get("source", ""))
        self.compiled.append(source)
        if FAIL_MARKER in source:
            lines = source.splitlines()
            line = next((n for n, text in enumerate(lines, start=1) if FAIL_MARKER in text), 1)
            return httpx.Response(
                422,
                json={
                    "diagnostics": [
                        {
                            "message": f"unknown function `{FAIL_MARKER.lstrip('#')}`",
                            "line": line,
                            "column": 1,
                            "severity": "error",
                        }
                    ]
                },
            )
        if body.get("output") == "svg":
            pages = [FAKE_SVG.format(page=n) for n in range(1, self.pages + 1)]
            return httpx.Response(200, json={"pages": pages})
        return httpx.Response(200, content=self.pdf, headers={"Content-Type": "application/pdf"})


def _multipart(request: httpx.Request) -> dict[str, tuple[str, bytes, str]]:
    """Each part as `name -> (filename, bytes, content type)`, binary payloads intact."""
    content_type = request.headers.get("content-type", "")
    _, _, boundary = content_type.partition("boundary=")
    if not boundary:
        return {}
    fields: dict[str, tuple[str, bytes, str]] = {}
    for chunk in request.content.split(b"--" + boundary.strip('"').encode())[1:-1]:
        head, _, body = chunk.lstrip(b"\r\n").partition(b"\r\n\r\n")
        headers = _part_headers(head)
        disposition = headers.get("content-disposition", "")
        name = _quoted(disposition, "name")
        if name:
            fields[name] = (
                _quoted(disposition, "filename") or "",
                body.removesuffix(b"\r\n"),
                headers.get("content-type", "text/plain"),
            )
    return fields


def _part_headers(head: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in head.decode("latin-1").splitlines():
        key, _, value = line.partition(":")
        if value:
            headers[key.strip().lower()] = value.strip()
    return headers


def _quoted(disposition: str, key: str) -> str:
    marker = f'{key}="'
    start = disposition.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    return disposition[start : disposition.find('"', start)]


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
    rows = _filter(rows, url)
    limit = url.params.get("limit")
    return rows[: int(limit)] if limit else rows


def _aggregate(rows: list[dict[str, Any]], url: httpx.URL) -> list[dict[str, Any]]:
    """`aggregate[count]=id`, with `groupBy` when it is asked for. Counts are strings."""
    matched = _filter(rows, url)
    group_by = url.params.get("groupBy")
    if not group_by:
        return [{"count": {"id": str(len(matched))}}]
    counts: dict[Any, int] = {}
    for row in matched:
        counts[row.get(group_by)] = counts.get(row.get(group_by), 0) + 1
    return [{group_by: key, "count": {"id": str(total)}} for key, total in counts.items()]


def _filter(rows: list[dict[str, Any]], url: httpx.URL) -> list[dict[str, Any]]:
    raw = url.params.get("filter")
    if not raw:
        return rows
    for field, condition in json.loads(raw).items():
        if not isinstance(condition, dict):
            continue
        if "_eq" in condition:
            rows = [row for row in rows if row.get(field) == condition["_eq"]]
        if "_in" in condition:
            rows = [row for row in rows if row.get(field) in condition["_in"]]
    return rows


def _error(status: int, message: str, code: str) -> httpx.Response:
    return httpx.Response(
        status, json={"errors": [{"message": message, "extensions": {"code": code}}]}
    )
