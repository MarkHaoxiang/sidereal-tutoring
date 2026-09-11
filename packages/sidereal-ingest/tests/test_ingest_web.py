from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sidereal_core.models import DocumentKind
from sidereal_ingest.base import IngestError
from sidereal_ingest.cache import FetchCache
from sidereal_ingest.ratelimit import TokenBucket
from sidereal_ingest.web import HttpxFetcher, WebPageIngester, extract

URL = "https://example.test/simultaneous-equations"

FIXTURES = Path(__file__).parent / "fixtures"


class RecordingFetcher:
    def __init__(self, body: str) -> None:
        self.body = body
        self.urls: list[str] = []

    async def fetch(self, url: str) -> str:
        self.urls.append(url)
        return self.body


async def test_ingest_extracts_title_and_visible_text() -> None:
    fetcher = RecordingFetcher((FIXTURES / "article.html").read_text())

    draft = await WebPageIngester(fetcher).ingest(URL)

    assert fetcher.urls == [URL]
    assert draft.kind is DocumentKind.WEB_PAGE
    assert draft.title == "Simultaneous equations"
    assert draft.source_url == URL
    assert draft.text == (
        "Simultaneous equations\nTwo equations, two unknowns.\nSubstitute, then solve."
    )


async def test_a_non_http_source_is_rejected() -> None:
    ingester = WebPageIngester(RecordingFetcher(""))

    assert not ingester.supports("downloads/page.html")
    with pytest.raises(IngestError):
        await ingester.ingest("downloads/page.html")


def test_extract_survives_a_page_with_no_title() -> None:
    title, text = extract("<html><body><p>Bare</p></body></html>")

    assert title == ""
    assert text == "Bare"


async def test_fetcher_caches_by_url_and_only_fetches_once(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="<html><body>hi</body></html>")

    cache = FetchCache(tmp_path / "web")
    fetcher = HttpxFetcher(
        cache=cache,
        bucket=TokenBucket(rate=1000.0),
        transport=httpx.MockTransport(handler),
    )

    first = await fetcher.fetch(URL)
    second = await fetcher.fetch(URL)
    await fetcher.aclose()

    assert first == second
    assert len(calls) == 1
    assert calls[0].headers["user-agent"].startswith("sidereal-tutoring/")
    assert cache.path_for(URL).is_file()


async def test_fetcher_rate_limits_before_each_uncached_request(tmp_path: Path) -> None:
    slept: list[float] = []
    now = [0.0]

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    bucket = TokenBucket(rate=1.0, capacity=1.0, clock=lambda: now[0], sleep=sleep)
    fetcher = HttpxFetcher(
        cache=FetchCache(tmp_path / "web"),
        bucket=bucket,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<p>ok</p>")),
    )

    await fetcher.fetch("https://example.test/a")
    await fetcher.fetch("https://example.test/b")
    await fetcher.aclose()

    assert slept == [1.0]


async def test_an_http_failure_is_an_ingest_error(tmp_path: Path) -> None:
    fetcher = HttpxFetcher(
        cache=FetchCache(tmp_path / "web"),
        bucket=TokenBucket(rate=1000.0),
        transport=httpx.MockTransport(lambda _: httpx.Response(404)),
    )

    with pytest.raises(IngestError):
        await fetcher.fetch(URL)
    await fetcher.aclose()
