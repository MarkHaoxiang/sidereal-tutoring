from __future__ import annotations

import httpx
import pytest
from sidereal_core.directus import DirectusClient, DirectusError
from sidereal_core.testing import FakeDirectus

BASE_URL = "http://directus.test"
FILE_ID = "22222222-2222-4222-8222-222222222222"


async def test_download_file_returns_the_stored_name_and_the_bytes() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("Lesson 3 notes.txt", b"Factorising quadratics.")

    async with fake.client() as client:
        name, content = await client.download_file(file_id)

    assert name == "Lesson 3 notes.txt"
    assert content == b"Factorising quadratics."
    paths = [request.url.path for request in fake.requests]
    assert paths == [f"/files/{file_id}", f"/assets/{file_id}"]
    assert fake.requests[-1].url.params["download"] == "true"


async def test_download_file_prefers_the_files_row_over_content_disposition() -> None:
    """Directus's header is a courtesy; `filename_download` is the row's own field."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/files/{FILE_ID}":
            return httpx.Response(
                200, json={"data": {"id": FILE_ID, "filename_download": "worksheet.pdf"}}
            )
        return httpx.Response(
            200,
            content=b"%PDF-1.4",
            headers={"Content-Disposition": 'attachment; filename="c4ca4238a0b9.pdf"'},
        )

    async with DirectusClient(BASE_URL, "tok", transport=httpx.MockTransport(handler)) as client:
        name, content = await client.download_file(FILE_ID)

    assert name == "worksheet.pdf"
    assert content == b"%PDF-1.4"


async def test_download_file_reports_a_directus_rejection() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        with pytest.raises(DirectusError) as raised:
            await client.download_file(FILE_ID)

    assert raised.value.status == 404


async def test_get_file_reads_the_files_route_not_items() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("notes.docx", b"x", media_type="application/msword")

    async with fake.client() as client:
        row = await client.get_file(file_id)

    assert row.filename_download == "notes.docx"
    assert row.type == "application/msword"
    assert row.filesize == 1
    assert fake.requests[0].url.path == f"/files/{file_id}"
