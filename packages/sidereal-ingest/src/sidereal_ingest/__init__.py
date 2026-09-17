from sidereal_core.models import DocumentDraft, DocumentKind

from sidereal_ingest.base import Ingester, IngestError, pick
from sidereal_ingest.cache import FetchCache
from sidereal_ingest.documents import (
    FILE_SUFFIXES,
    DocumentError,
    FileSource,
    PathSource,
    ScanSource,
    Source,
    TextSource,
    UrlSource,
    create_document,
    process_document,
)
from sidereal_ingest.pdf import (
    MAX_PAGE_IMAGES,
    Figure,
    PageImage,
    figure,
    needs_page_images,
    page_count,
    page_images,
    raster_pages,
)
from sidereal_ingest.ratelimit import TokenBucket
from sidereal_ingest.scan import MAX_PAGES, ScanFile, ScanIngester
from sidereal_ingest.settings import DEFAULT_DATA_DIR, data_dir
from sidereal_ingest.submissions import transcribe_submission
from sidereal_ingest.transcribe import (
    Confidence,
    FakeTranscriber,
    Page,
    PaperQuestion,
    TranscribedQuestion,
    Transcriber,
    Transcription,
    TranscriptionResult,
)
from sidereal_ingest.transcript import TranscriptIngester, strip_timestamps
from sidereal_ingest.upload import UploadIngester
from sidereal_ingest.web import Fetcher, HttpxFetcher, WebPageIngester

__all__ = [
    "DEFAULT_DATA_DIR",
    "FILE_SUFFIXES",
    "MAX_PAGES",
    "MAX_PAGE_IMAGES",
    "Confidence",
    "DocumentDraft",
    "DocumentError",
    "DocumentKind",
    "FakeTranscriber",
    "FetchCache",
    "Fetcher",
    "Figure",
    "FileSource",
    "HttpxFetcher",
    "IngestError",
    "Ingester",
    "Page",
    "PageImage",
    "PaperQuestion",
    "PathSource",
    "ScanFile",
    "ScanIngester",
    "ScanSource",
    "Source",
    "TextSource",
    "TokenBucket",
    "TranscribedQuestion",
    "Transcriber",
    "TranscriptIngester",
    "Transcription",
    "TranscriptionResult",
    "UploadIngester",
    "UrlSource",
    "WebPageIngester",
    "create_document",
    "data_dir",
    "default_ingesters",
    "figure",
    "needs_page_images",
    "page_count",
    "page_images",
    "pick",
    "process_document",
    "raster_pages",
    "strip_timestamps",
    "transcribe_submission",
]


def default_ingesters(fetcher: Fetcher | None = None) -> list[Ingester]:
    """Transcripts first: `.txt` is claimed by both the transcript and upload ingesters."""
    return [
        TranscriptIngester(),
        WebPageIngester(fetcher if fetcher is not None else HttpxFetcher()),
        UploadIngester(),
    ]
