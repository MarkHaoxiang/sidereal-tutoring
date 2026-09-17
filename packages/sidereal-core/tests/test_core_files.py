from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from sidereal_core.directus import DirectusClient, DirectusError
from sidereal_core.files import release_uploads
from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus

BASE_URL = "http://directus.test"
FILE_ID = "22222222-2222-4222-8222-222222222222"


async def test_a_file_is_read_off_the_files_route_and_the_bytes_off_assets() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file(
        "Lesson 3 notes.txt", b"Factorising quadratics.", media_type="text/plain"
    )

    async with fake.client() as client:
        row = await client.get_file(file_id)
        name, content = await client.download_file(file_id)

    assert row.filename_download == "Lesson 3 notes.txt"
    assert row.type == "text/plain"
    assert row.filesize == len(b"Factorising quadratics.")
    assert name == "Lesson 3 notes.txt"
    assert content == b"Factorising quadratics."
    paths = [request.url.path for request in fake.requests]
    assert paths == [f"/files/{file_id}", f"/files/{file_id}", f"/assets/{file_id}"]
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


async def test_upload_file_posts_the_bytes_and_reads_them_back() -> None:
    fake = FakeDirectus()
    pdf = b"%PDF-1.7\nbinary\x00\r\nbytes\n%%EOF\n"

    async with fake.client() as client:
        uploaded = await client.upload_file(
            "quadratics-week-3.pdf", pdf, "application/pdf", title="Quadratics: week 3"
        )
        name, content = await client.download_file(uploaded.id)

    assert uploaded.filename_download == "quadratics-week-3.pdf"
    assert uploaded.title == "Quadratics: week 3"
    assert uploaded.type == "application/pdf"
    assert (name, content) == ("quadratics-week-3.pdf", pdf)
    assert fake.requests[0].url.path == "/files"


async def test_uploads_pass_to_the_caller_before_their_owner_goes() -> None:
    fake = FakeDirectus()
    owner = fake.seed(Collection.DIRECTUS_USERS, {"email": "leaving@example.test"})
    fake.register_file("working.jpg", b"jpeg", uploaded_by=owner["id"])
    keeper = uuid4()

    async with fake.client() as client:
        released = await release_uploads(client, UUID(owner["id"]), to=keeper)
        await client.delete_user(owner["id"])

    assert [file.filename_download for file in released] == ["working.jpg"]
    assert [row["uploaded_by"] for row, _ in fake.files.values()] == [str(keeper)]


async def test_a_user_with_uploads_still_pointing_at_them_cannot_be_deleted() -> None:
    """The constraint the release step exists for, as Directus enforces it unloosened."""
    fake = FakeDirectus()
    owner = fake.seed(Collection.DIRECTUS_USERS, {"email": "leaving@example.test"})
    fake.register_file("working.jpg", b"jpeg", uploaded_by=owner["id"])

    async with fake.client() as client:
        with pytest.raises(DirectusError, match="directus_files_uploaded_by_foreign"):
            await client.delete_user(owner["id"])


async def test_a_file_the_caller_may_not_own_is_released_to_nobody() -> None:
    fake = FakeDirectus()
    owner = fake.seed(Collection.DIRECTUS_USERS, {"email": "leaving@example.test"})
    file_id = fake.register_file("working.jpg", b"jpeg", uploaded_by=owner["id"])
    refused: list[str] = []

    inner = fake.handle

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode() if request.content else ""
        if request.method == "PATCH" and '"uploaded_by":"' in body:
            refused.append(body)
            return httpx.Response(403, json={"errors": [{"message": "no"}]})
        return inner(request)

    fake.handle = handler  # type: ignore[method-assign]

    async with fake.client() as client:
        await release_uploads(client, UUID(owner["id"]), to=uuid4())

    assert refused
    assert fake.files[file_id][0]["uploaded_by"] is None
