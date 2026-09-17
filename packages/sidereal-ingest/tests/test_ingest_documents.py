from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sidereal_core.directus import DirectusClient
from sidereal_core.models import Collection, DocumentDraft, DocumentKind, DocumentStatus
from sidereal_core.testing import BASE_URL, DEFAULT_TOKEN, FakeDirectus
from sidereal_ingest.base import Ingester, IngestError
from sidereal_ingest.documents import (
    FileSource,
    PathSource,
    TextSource,
    UrlSource,
    create_document,
    process_document,
)
from sidereal_ingest.transcript import TranscriptIngester
from sidereal_ingest.upload import UploadIngester
from sidereal_ingest.web import WebPageIngester

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = "<html><head><title>Indices</title></head><body><p>Powers of ten.</p></body></html>"


class StubFetcher:
    async def fetch(self, url: str) -> str:
        return PAGE


class FailingFetcher:
    def __init__(self, status: int | None) -> None:
        self.status = status

    async def fetch(self, url: str) -> str:
        raise IngestError(f"{url}: rejected", status=self.status)


def ingesters(fetcher: StubFetcher | FailingFetcher | None = None) -> list[Ingester]:
    return [
        TranscriptIngester(),
        WebPageIngester(fetcher if fetcher is not None else StubFetcher()),
        UploadIngester(),
    ]


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SIDEREAL_DATA_DIR", str(tmp_path))
    return tmp_path


def gone(path: Path) -> bool:
    return not path.exists() and not path.parent.exists()


def is_empty(directory: Path) -> bool:
    return not list(directory.iterdir())


class RecordingIngester:
    """Remembers the path it was handed, so a test can check nothing survives the read."""

    kind = DocumentKind.TRANSCRIPT

    def __init__(self) -> None:
        self.sources: list[str] = []

    def supports(self, source: str) -> bool:
        return True

    async def ingest(self, source: str) -> DocumentDraft:
        self.sources.append(source)
        return await TranscriptIngester().ingest(source)


async def test_a_directus_file_is_downloaded_then_read(data_dir: Path) -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("lesson.vtt", (FIXTURES / "lesson.vtt").read_bytes())

    async with fake.client() as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, ingesters(), created.id)

    assert created.status is DocumentStatus.PENDING
    assert created.title == "lesson"
    assert created.kind is DocumentKind.TRANSCRIPT
    assert document.status is DocumentStatus.READY
    assert document.text is not None
    assert document.error is None


async def test_the_downloaded_copy_does_not_outlive_the_read(data_dir: Path) -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("lesson.vtt", (FIXTURES / "lesson.vtt").read_bytes())
    recorder = RecordingIngester()

    async with fake.client() as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, [recorder], created.id)

    assert document.status is DocumentStatus.READY
    downloaded = Path(recorder.sources[0])
    assert downloaded.name == "lesson.vtt"
    assert gone(downloaded)
    assert is_empty(data_dir)


async def test_an_upload_is_filed_as_an_upload_and_keeps_the_filename() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("question-bank.pdf", (FIXTURES / "question-bank.pdf").read_bytes())

    async with fake.client() as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, ingesters(), created.id)

    assert document.kind is DocumentKind.UPLOAD
    assert document.text == "   Quadratic equations: practice set\n   Solve x^2 - 5x + 6 = 0"
    assert document.metadata["filename"] == "question-bank.pdf"
    assert "title_source" not in document.metadata


async def test_a_file_type_we_cannot_read_fails_with_the_types_we_can() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("marks.xlsx", b"PK\x03\x04")

    async with fake.client() as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, ingesters(), created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error is not None
    assert document.error.startswith("marks.xlsx cannot be read.")
    assert ".pdf" in document.error and ".vtt" in document.error


async def test_a_missing_file_fails_with_a_library_message() -> None:
    fake = FakeDirectus()
    row = fake.seed(
        Collection.DOCUMENTS,
        {
            "title": "Gone",
            "kind": "upload",
            "status": "pending",
            "file": "33333333-3333-4333-8333-333333333333",
        },
    )

    async with fake.client() as client:
        document = await process_document(client, ingesters(), UUID(row["id"]))

    assert document.status is DocumentStatus.FAILED
    assert document.error == (
        "The file could not be downloaded from your material library (HTTP 404)."
    )


async def test_pasted_text_is_ready_without_any_ingestion() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(client, TextSource("Factorise x^2 - 5x + 6."))
        document = await process_document(client, [], created.id)

    assert created.kind is DocumentKind.UPLOAD
    assert created.title.startswith("Pasted text ")
    assert document.status is DocumentStatus.READY
    assert document.text == "Factorise x^2 - 5x + 6."
    assert document.title == created.title


async def test_a_url_takes_its_title_from_the_page() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(client, UrlSource("https://example.test/indices"))
        document = await process_document(client, ingesters(), created.id)

    assert created.title == "example.test"
    assert created.kind is DocumentKind.WEB_PAGE
    assert document.title == "Indices"
    assert document.text == "Powers of ten."
    assert document.source_url == "https://example.test/indices"


async def test_a_title_the_tutor_chose_survives_processing() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(
            client, UrlSource("https://example.test/indices"), title="Indices revision"
        )
        document = await process_document(client, ingesters(), created.id)

    assert document.title == "Indices revision"


async def test_a_link_that_answers_with_an_error_says_so() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(client, UrlSource("https://example.test/missing"))
        document = await process_document(client, ingesters(FailingFetcher(404)), created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error == "The link could not be fetched (HTTP 404)."


async def test_a_link_that_never_answers_says_so() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(client, UrlSource("https://nowhere.test/page"))
        document = await process_document(client, ingesters(FailingFetcher(None)), created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error == "The link could not be fetched — the site did not answer."


async def test_a_local_path_is_read_in_place(data_dir: Path) -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(client, PathSource(str(FIXTURES / "tutor-notes.txt")))
        document = await process_document(client, ingesters(), created.id)

    assert document.status is DocumentStatus.READY
    assert document.text is not None
    assert document.text.startswith("Needs more practice")
    assert document.metadata["path"] == str(FIXTURES / "tutor-notes.txt")


async def test_a_damaged_file_says_the_file_could_not_be_read() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("worksheet.pdf", b"not really a pdf")

    async with fake.client() as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, ingesters(), created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error is not None
    assert document.error.startswith("The file could not be read (")


async def test_a_download_that_cannot_be_reached_is_reported_as_such() -> None:
    """Only the asset route is cut off, so the row can still record why it failed."""
    fake = FakeDirectus()
    file_id = fake.register_file("lesson.vtt", (FIXTURES / "lesson.vtt").read_bytes())

    def no_assets(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/assets/"):
            raise httpx.ConnectError("connection refused", request=request)
        return fake.handle(request)

    async with DirectusClient(
        BASE_URL, DEFAULT_TOKEN, transport=httpx.MockTransport(no_assets)
    ) as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, ingesters(), created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error == (
        "The file could not be downloaded: the material library is not reachable."
    )


async def test_a_file_that_cannot_be_written_to_disk_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("lesson.vtt", (FIXTURES / "lesson.vtt").read_bytes())

    def full_disk(self: Path, data: bytes) -> int:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "write_bytes", full_disk)

    async with fake.client() as client:
        created = await create_document(client, FileSource(UUID(file_id)))
        document = await process_document(client, ingesters(), created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error is not None
    assert document.error.startswith("The file could not be saved to this machine (")


async def test_a_row_with_no_source_at_all_fails() -> None:
    fake = FakeDirectus()
    row = fake.seed(Collection.DOCUMENTS, {"title": "Empty", "kind": "upload", "status": "pending"})

    async with fake.client() as client:
        document = await process_document(client, ingesters(), UUID(row["id"]))

    assert document.status is DocumentStatus.FAILED
    assert document.error == "There is nothing to read here: no file, no link and no text."


async def test_processing_a_failed_row_again_clears_the_error() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(client, UrlSource("https://example.test/indices"))
        failed = await process_document(client, ingesters(FailingFetcher(500)), created.id)
        retried = await process_document(client, ingesters(), created.id)

    assert failed.status is DocumentStatus.FAILED
    assert retried.status is DocumentStatus.READY
    assert retried.error is None
    assert retried.title == "Indices"


async def test_a_caller_can_pin_the_kind_a_row_is_filed_under() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        created = await create_document(
            client, UrlSource("https://example.test/papers"), kind=DocumentKind.QUESTION_BANK
        )
        document = await process_document(client, ingesters(), created.id)

    assert document.kind is DocumentKind.QUESTION_BANK
