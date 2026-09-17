"""Typed async access to the Directus REST API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any, Self, TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from sidereal_core.models import (
    DirectusFile,
    DirectusLicense,
    DirectusRole,
    DirectusServerInfo,
    DirectusUser,
    Draft,
)

M = TypeVar("M", bound=BaseModel)

DEFAULT_TIMEOUT = 10.0


class DirectusErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    message: str = ""
    extensions: dict[str, Any] = Field(default_factory=dict)

    @property
    def code(self) -> str | None:
        code = self.extensions.get("code")
        return code if isinstance(code, str) else None


class DirectusClientError(Exception):
    """Anything that stopped a Directus call from producing a validated model."""


class DirectusUnavailableError(DirectusClientError):
    """Directus could not be reached at all."""


class DirectusError(DirectusClientError):
    def __init__(
        self,
        status: int,
        errors: Sequence[DirectusErrorDetail] = (),
        message: str | None = None,
    ) -> None:
        self.status = status
        self.errors = tuple(errors)
        summary = message or "; ".join(error.message for error in self.errors if error.message)
        super().__init__(f"Directus {status}: {summary}" if summary else f"Directus {status}")

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(code for error in self.errors if (code := error.code) is not None)


class DirectusClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self.base_url, transport=transport, timeout=timeout
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_items(
        self,
        collection: str,
        model: type[M],
        *,
        filter: Mapping[str, Any] | None = None,
        limit: int | None = None,
        sort: Sequence[str] | None = None,
    ) -> list[M]:
        return await self._list(
            f"/items/{collection}", model, filter=filter, limit=limit, sort=sort
        )

    async def get_item(self, collection: str, model: type[M], item_id: str | UUID) -> M:
        data = await self._request("GET", f"/items/{collection}/{item_id}")
        return model.model_validate(data)

    async def create_item(
        self, collection: str, model: type[M], data: Draft | Mapping[str, Any]
    ) -> M:
        created = await self._request("POST", f"/items/{collection}", json=_body(data))
        return model.model_validate(created)

    async def update_item(
        self,
        collection: str,
        model: type[M],
        item_id: str | UUID,
        data: Draft | Mapping[str, Any],
    ) -> M:
        updated = await self._request("PATCH", f"/items/{collection}/{item_id}", json=_body(data))
        return model.model_validate(updated)

    async def delete_item(self, collection: str, item_id: str | UUID) -> None:
        await self._request("DELETE", f"/items/{collection}/{item_id}")

    async def me(self) -> DirectusUser:
        # `admin_access` is on no row Directus will show: `/policies/me/globals` is the answer.
        data, admin_access = await asyncio.gather(
            self._request("GET", "/users/me"), self._admin_access()
        )
        if not isinstance(data, dict):
            raise DirectusError(200, message="/users/me: expected a user")
        return DirectusUser.model_validate({**data, "admin_access": admin_access})

    async def _admin_access(self) -> bool:
        """A Directus that will not answer this is one where the caller is not an admin."""
        try:
            answer = await self._request("GET", "/policies/me/globals")
        except DirectusClientError:
            return False
        return isinstance(answer, dict) and answer.get("admin_access") is True

    async def server_info(self) -> DirectusServerInfo:
        return DirectusServerInfo.model_validate(await self._request("GET", "/server/info"))

    async def license_info(self) -> DirectusLicense:
        return DirectusLicense.model_validate(await self._request("GET", "/license"))

    async def list_roles(self) -> list[DirectusRole]:
        """`directus_roles` is a system collection: it answers on `/roles`, not `/items`."""
        return await self._list("/roles", DirectusRole)

    async def find_role(self, name: str) -> DirectusRole | None:
        roles = await self._list("/roles", DirectusRole, filter={"name": {"_eq": name}}, limit=1)
        return roles[0] if roles else None

    async def list_users(
        self,
        *,
        filter: Mapping[str, Any] | None = None,
        limit: int | None = None,
        sort: Sequence[str] | None = None,
    ) -> list[DirectusUser]:
        return await self._list("/users", DirectusUser, filter=filter, limit=limit, sort=sort)

    async def get_user(self, user_id: str | UUID) -> DirectusUser:
        data = await self._request("GET", f"/users/{user_id}")
        return DirectusUser.model_validate(data)

    async def create_user(self, data: Mapping[str, Any]) -> DirectusUser:
        """`directus_users` is a system collection: it answers on `/users`, not `/items`."""
        created = await self._request("POST", "/users", json=dict(data))
        return DirectusUser.model_validate(created)

    async def update_user(self, user_id: str | UUID, data: Mapping[str, Any]) -> DirectusUser:
        updated = await self._request("PATCH", f"/users/{user_id}", json=dict(data))
        return DirectusUser.model_validate(updated)

    async def delete_user(self, user_id: str | UUID) -> None:
        await self._request("DELETE", f"/users/{user_id}")

    async def create_related(
        self, collection: str, item_id: str | UUID, field: str, data: Mapping[str, Any]
    ) -> UUID:
        """Create the related row through the owner's own field, and answer with its id.

        A `POST /users` a caller cannot read back answers 204 with no body, so the row is
        created and linked in one write on the owner instead.
        """
        body = await self._request(
            "PATCH",
            f"/items/{collection}/{item_id}",
            params={"fields": f"{field}.id"},
            json={field: dict(data)},
        )
        related = body.get(field) if isinstance(body, dict) else None
        identifier = related.get("id") if isinstance(related, dict) else related
        if not isinstance(identifier, str | UUID):
            raise DirectusError(200, message=f"/items/{collection}: no {field} in the answer")
        return UUID(str(identifier))

    async def get_file(self, file_id: str | UUID) -> DirectusFile:
        """`directus_files` is a system collection: it answers on `/files`, not `/items`."""
        data = await self._request("GET", f"/files/{file_id}")
        return DirectusFile.model_validate(data)

    async def list_files(
        self,
        *,
        filter: Mapping[str, Any] | None = None,
        limit: int | None = None,
        sort: Sequence[str] | None = None,
    ) -> list[DirectusFile]:
        return await self._list("/files", DirectusFile, filter=filter, limit=limit, sort=sort)

    async def update_file(self, file_id: str | UUID, data: Mapping[str, Any]) -> DirectusFile:
        updated = await self._request("PATCH", f"/files/{file_id}", json=dict(data))
        return DirectusFile.model_validate(updated)

    async def delete_file(self, file_id: str | UUID) -> None:
        await self._request("DELETE", f"/files/{file_id}")

    async def upload_file(
        self, filename: str, content: bytes, content_type: str, *, title: str | None = None
    ) -> DirectusFile:
        """Multipart, because `/files` takes the bytes themselves and not a JSON body."""
        data = {"title": title} if title is not None else {}
        uploaded = await self._request(
            "POST", "/files", data=data, files={"file": (filename, content, content_type)}
        )
        return DirectusFile.model_validate(uploaded)

    async def download_file(self, file_id: str | UUID) -> tuple[str, bytes]:
        """The asset's bytes, and the name Directus says it was uploaded under."""
        name = (await self.get_file(file_id)).filename_download
        response = await self._send("GET", f"/assets/{file_id}", params={"download": "true"})
        return name, response.content

    async def count_items(self, collection: str, *, filter: Mapping[str, Any] | None = None) -> int:
        rows = await self._aggregate(f"/items/{collection}", filter=filter)
        return _count(rows[0]) if rows else 0

    async def count_users(self, *, filter: Mapping[str, Any] | None = None) -> int:
        rows = await self._aggregate("/users", filter=filter)
        return _count(rows[0]) if rows else 0

    async def count_items_by(
        self, collection: str, group_by: str, *, filter: Mapping[str, Any] | None = None
    ) -> dict[str, int]:
        """One count per distinct value of `group_by`. Rows with no value are left out."""
        rows = await self._aggregate(f"/items/{collection}", filter=filter, group_by=group_by)
        return {str(key): _count(row) for row in rows if (key := row.get(group_by)) is not None}

    async def _aggregate(
        self,
        path: str,
        *,
        filter: Mapping[str, Any] | None = None,
        group_by: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {"aggregate[count]": "id"}
        if filter is not None:
            params["filter"] = json.dumps(filter)
        if group_by is not None:
            params["groupBy"] = group_by
        data = await self._request("GET", path, params=params)
        if not isinstance(data, list):
            raise DirectusError(200, message=f"{path}: expected aggregate rows")
        return [row for row in data if isinstance(row, dict)]

    async def _list(
        self,
        path: str,
        model: type[M],
        *,
        filter: Mapping[str, Any] | None = None,
        limit: int | None = None,
        sort: Sequence[str] | None = None,
    ) -> list[M]:
        params: dict[str, str | int] = {}
        if filter is not None:
            params["filter"] = json.dumps(filter)
        if limit is not None:
            params["limit"] = limit
        if sort:
            params["sort"] = ",".join(sort)
        data = await self._request("GET", path, params=params)
        if not isinstance(data, list):
            raise DirectusError(200, message=f"{path}: expected a list of items")
        return [model.model_validate(item) for item in data]

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        response = await self._send(method, path, params=params, json=json, data=data, files=files)
        if response.status_code == httpx.codes.NO_CONTENT or not response.content:
            return None

        body = response.json()
        if not isinstance(body, dict) or "data" not in body:
            raise DirectusError(response.status_code, message=f"{path}: no data envelope")
        return body["data"]

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        json: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes, str]] | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = await self._client.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                json=json,
                data=dict(data) if data else None,
                files=dict(files) if files else None,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise DirectusUnavailableError(f"{self.base_url}{path}: {exc}") from exc
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise DirectusError(response.status_code, _details(response))
        return response


def _count(row: Mapping[str, Any]) -> int:
    """Directus sends an aggregate count as a string, and as null for an empty collection."""
    count = row.get("count")
    value = count.get("id") if isinstance(count, dict) else None
    if not isinstance(value, str | int):
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _body(data: Draft | Mapping[str, Any]) -> dict[str, Any]:
    return data.payload() if isinstance(data, Draft) else dict(data)


def _details(response: httpx.Response) -> tuple[DirectusErrorDetail, ...]:
    try:
        body = response.json()
    except ValueError:
        return ()
    if not isinstance(body, dict):
        return ()
    errors = body.get("errors")
    if not isinstance(errors, list):
        return ()
    return tuple(DirectusErrorDetail.model_validate(error) for error in errors)
