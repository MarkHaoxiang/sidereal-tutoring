from __future__ import annotations

import base64
from datetime import date

import httpx
import pytest
from sidereal_core.canonical import (
    CanonicalFigureBlock,
    CanonicalPaper,
    CanonicalQuestion,
    RenderKind,
)
from sidereal_core.settings import DEFAULT_TYPESET_URL, typeset_settings
from sidereal_core.testing import FAIL_MARKER, FAKE_PDF, FakeTypeset
from sidereal_core.typeset import (
    MAX_ASSET_BYTES,
    MAX_ASSETS_BYTES,
    TypesetClient,
    TypesetError,
    TypesetUnavailableError,
)

SOURCE = "= Week 3\n$x^2 - 5x + 6$\n"
FIGURE = b"\x89PNG\r\n\x1a\n not a real image, only bytes"
WITH_FIGURE = CanonicalPaper(
    title="Physics 1",
    questions=(
        CanonicalQuestion(
            number="1", blocks=(CanonicalFigureBlock(asset="figure-1.png", width_mm=70),)
        ),
    ),
)


async def test_a_source_becomes_a_pdf_and_svg_pages() -> None:
    fake = FakeTypeset(pages=3)

    async with fake.client() as client:
        assert await client.healthy() is True
        pdf = await client.compile_pdf(SOURCE)
        pages = await client.render_svg(SOURCE)

    assert pdf == FAKE_PDF
    assert len(pages) == 3
    assert pages[0].startswith("<svg")
    assert fake.compiled == [SOURCE, SOURCE]


async def test_the_body_comes_back_wrapped_in_the_house_template() -> None:
    fake = FakeTypeset()

    async with fake.client() as client:
        source = await client.wrap_homework(
            title="Quadratics: week 3",
            student="A. Tutee",
            due=date(2026, 9, 25),
            body="#question[Factorise $x^2 - 5x + 6$.]",
        )

    assert "Quadratics: week 3" in source
    assert "#question[Factorise $x^2 - 5x + 6$.]" in source
    assert fake.wrapped[0]["kind"] == "homework"
    assert fake.wrapped[0]["due"] == "2026-09-25"


async def test_a_source_that_will_not_compile_carries_the_diagnostics() -> None:
    async with FakeTypeset().client() as client:
        with pytest.raises(TypesetError) as raised:
            await client.compile_pdf(f"= Week 3\n{FAIL_MARKER}\n")

    assert raised.value.status == 422
    assert [diagnostic.line for diagnostic in raised.value.diagnostics] == [2]
    assert "does-not-compile" in str(raised.value)


async def test_a_service_that_cannot_be_reached_is_its_own_error() -> None:
    fake = FakeTypeset()
    fake.unavailable = True

    async with fake.client() as client:
        assert await client.healthy() is False
        with pytest.raises(TypesetUnavailableError):
            await client.compile_pdf(SOURCE)


async def test_a_refusal_without_diagnostics_keeps_the_services_own_sentence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(413, json={"message": "source is larger than 256 KiB"})

    async with TypesetClient("http://typeset.test", transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(TypesetError, match="larger than 256 KiB") as raised:
            await c.compile_pdf(SOURCE)

    assert raised.value.status == 413
    assert raised.value.diagnostics == ()


def test_settings_default_and_override() -> None:
    assert typeset_settings({}).url == DEFAULT_TYPESET_URL
    assert typeset_settings({"SIDEREAL_TYPESET_URL": "http://host:1/"}).url == "http://host:1"


async def test_a_figure_s_bytes_go_over_as_base64_under_the_name_it_asked_for() -> None:
    fake = FakeTypeset()

    async with fake.client() as client:
        await client.render(RenderKind.PAPER, WITH_FIGURE, assets={"figure-1.png": FIGURE})
        await client.render(RenderKind.PAPER, WITH_FIGURE)

    assert fake.rendered[0]["assets"] == {"figure-1.png": base64.b64encode(FIGURE).decode()}
    assert base64.b64decode(fake.rendered[0]["assets"]["figure-1.png"]) == FIGURE
    assert "assets" not in fake.rendered[1]


async def test_an_asset_over_the_services_limit_is_refused_before_it_is_sent() -> None:
    fake = FakeTypeset()

    async with fake.client() as client:
        with pytest.raises(TypesetError, match=r"figure-1\.png") as one:
            await client.render(
                RenderKind.PAPER, WITH_FIGURE, assets={"figure-1.png": b"x" * (MAX_ASSET_BYTES + 1)}
            )
        with pytest.raises(TypesetError, match="the assets are larger") as together:
            await client.render(
                RenderKind.PAPER,
                WITH_FIGURE,
                assets={
                    f"figure-{n}.png": b"x" * MAX_ASSET_BYTES
                    for n in range(MAX_ASSETS_BYTES // MAX_ASSET_BYTES + 1)
                },
            )

    assert one.value.status == 413
    assert together.value.status == 413
    assert fake.rendered == []
