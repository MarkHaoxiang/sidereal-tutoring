"""Typed async access to the typeset service, which turns Typst source into a document."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict

# The service's own compile timeout is 10s; the client waits longer than the answer can take.
DEFAULT_TIMEOUT = 30.0
HOMEWORK_KIND = "homework"


class Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    message: str
    line: int | None = None
    column: int | None = None
    severity: str = "error"

    def __str__(self) -> str:
        where = "" if self.line is None else f"line {self.line}"
        if where and self.column is not None:
            where = f"{where}, column {self.column}"
        return f"{where}: {self.message}" if where else self.message


class TypesetClientError(Exception):
    """Anything that stopped a typeset call from producing a document."""


class TypesetUnavailableError(TypesetClientError):
    """The typeset service could not be reached at all."""


class TypesetError(TypesetClientError):
    """The typeset service refused the source. `diagnostics` is what the compiler said."""

    def __init__(
        self,
        status: int,
        diagnostics: Sequence[Diagnostic] = (),
        message: str | None = None,
    ) -> None:
        self.status = status
        self.diagnostics = tuple(diagnostics)
        summary = message or "\n".join(str(diagnostic) for diagnostic in self.diagnostics)
        super().__init__(summary or f"Typeset {status}")


class TypesetClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
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

    async def healthy(self) -> bool:
        try:
            await self._send("GET", "/healthz")
        except TypesetClientError:
            return False
        return True

    async def compile_pdf(self, source: str) -> bytes:
        response = await self._send("POST", "/compile", json={"source": source, "output": "pdf"})
        return response.content

    async def render_svg(self, source: str) -> list[str]:
        """One SVG string per page."""
        body = self._json(await self._send("POST", "/compile", {"source": source, "output": "svg"}))
        pages = body.get("pages")
        if not isinstance(pages, list) or not all(isinstance(page, str) for page in pages):
            raise TypesetError(200, message="/compile: no pages in the answer")
        return [str(page) for page in pages]

    async def wrap_homework(self, *, title: str, student: str, due: date | None, body: str) -> str:
        """The house template around a body, as the service alone knows how to write it."""
        answer = self._json(
            await self._send(
                "POST",
                "/template",
                {
                    "kind": HOMEWORK_KIND,
                    "title": title,
                    "student": student,
                    "due": None if due is None else due.isoformat(),
                    "body": body,
                },
            )
        )
        source = answer.get("source")
        if not isinstance(source, str):
            raise TypesetError(200, message="/template: no source in the answer")
        return source

    def _json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise TypesetError(response.status_code, message="the answer was not JSON") from exc
        if not isinstance(body, dict):
            raise TypesetError(response.status_code, message="the answer was not an object")
        return body

    async def _send(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            response = await self._client.request(method, f"{self.base_url}{path}", json=json)
        except httpx.HTTPError as exc:
            raise TypesetUnavailableError(f"{self.base_url}{path}: {exc}") from exc
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise TypesetError(response.status_code, *_failure(response))
        return response


def _failure(response: httpx.Response) -> tuple[tuple[Diagnostic, ...], str | None]:
    """The compiler's diagnostics when it gave any, else whatever sentence the service sent."""
    try:
        body = response.json()
    except ValueError:
        return (), response.text.strip()[:200] or None
    if not isinstance(body, dict):
        return (), None
    raw = body.get("diagnostics")
    if isinstance(raw, list):
        return tuple(Diagnostic.model_validate(item) for item in raw), None
    message = body.get("message") or body.get("error")
    return (), message if isinstance(message, str) else None
