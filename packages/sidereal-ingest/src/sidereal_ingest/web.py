from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx
from selectolax.lexbor import LexborHTMLParser
from sidereal_core.models import DocumentDraft, DocumentKind, DocumentStatus

from sidereal_ingest.base import IngestError
from sidereal_ingest.cache import FetchCache
from sidereal_ingest.ratelimit import TokenBucket
from sidereal_ingest.settings import data_dir

SCHEMES = ("http://", "https://")
USER_AGENT = "sidereal-tutoring/0.1 (+https://github.com/MarkHaoxiang/sidereal-tutoring)"
DEFAULT_RATE_PER_SECOND = 1.0
_DROPPED_TAGS = ["script", "style", "noscript", "template", "svg"]


@runtime_checkable
class Fetcher(Protocol):
    async def fetch(self, url: str) -> str: ...


class HttpxFetcher:
    """Rate-limited, cached HTTP. Every outbound fetch in this package goes through one."""

    def __init__(
        self,
        *,
        cache: FetchCache | None = None,
        bucket: TokenBucket | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._cache = cache if cache is not None else FetchCache(data_dir() / "web")
        self._bucket = bucket if bucket is not None else TokenBucket(DEFAULT_RATE_PER_SECOND)
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            transport=transport, timeout=timeout, follow_redirects=True
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch(self, url: str) -> str:
        cached = self._cache.read(url)
        if cached is not None:
            return cached
        await self._bucket.acquire()
        try:
            response = await self._client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IngestError(f"{url}: {exc}") from exc
        self._cache.write(url, response.text)
        return response.text


class WebPageIngester:
    kind = DocumentKind.WEB_PAGE

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    def supports(self, source: str) -> bool:
        return source.startswith(SCHEMES)

    async def ingest(self, source: str) -> DocumentDraft:
        if not self.supports(source):
            raise IngestError(f"{source!r}: not an http(s) URL")
        html = await self._fetcher.fetch(source)
        title, text = extract(html)
        return DocumentDraft(
            title=title or source,
            kind=self.kind,
            source_url=source,
            text=text,
            status=DocumentStatus.READY,
        )


def extract(html: str) -> tuple[str, str]:
    tree = LexborHTMLParser(html)
    tree.strip_tags(_DROPPED_TAGS)
    titles = tree.css("title")
    title = titles[0].text(strip=True) if titles else ""
    body = tree.body
    text = body.text(separator="\n", strip=True) if body is not None else ""
    return title, "\n".join(line for line in text.splitlines() if line.strip())
