from sidereal_core.models import DocumentDraft, DocumentKind

from sidereal_ingest.base import Ingester, IngestError, pick
from sidereal_ingest.cache import FetchCache
from sidereal_ingest.documents import (
    FILE_SUFFIXES,
    DocumentError,
    FileSource,
    PathSource,
    Source,
    TextSource,
    UrlSource,
    create_document,
    process_document,
)
from sidereal_ingest.ratelimit import TokenBucket
from sidereal_ingest.settings import DEFAULT_DATA_DIR, data_dir
from sidereal_ingest.transcript import TranscriptIngester, strip_timestamps
from sidereal_ingest.upload import UploadIngester
from sidereal_ingest.web import Fetcher, HttpxFetcher, WebPageIngester

__all__ = [
    "DEFAULT_DATA_DIR",
    "FILE_SUFFIXES",
    "DocumentDraft",
    "DocumentError",
    "DocumentKind",
    "FetchCache",
    "Fetcher",
    "FileSource",
    "HttpxFetcher",
    "IngestError",
    "Ingester",
    "PathSource",
    "Source",
    "TextSource",
    "TokenBucket",
    "TranscriptIngester",
    "UploadIngester",
    "UrlSource",
    "WebPageIngester",
    "create_document",
    "data_dir",
    "default_ingesters",
    "pick",
    "process_document",
    "strip_timestamps",
]


def default_ingesters(fetcher: Fetcher | None = None) -> list[Ingester]:
    """Transcripts first: `.txt` is claimed by both the transcript and upload ingesters."""
    return [
        TranscriptIngester(),
        WebPageIngester(fetcher if fetcher is not None else HttpxFetcher()),
        UploadIngester(),
    ]
