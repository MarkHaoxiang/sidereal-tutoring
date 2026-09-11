from sidereal_core.models import DocumentDraft, DocumentKind

from sidereal_ingest.base import Ingester, IngestError, pick
from sidereal_ingest.cache import FetchCache
from sidereal_ingest.ratelimit import TokenBucket
from sidereal_ingest.settings import DEFAULT_DATA_DIR, data_dir
from sidereal_ingest.transcript import TranscriptIngester, strip_timestamps
from sidereal_ingest.upload import UploadIngester
from sidereal_ingest.web import Fetcher, HttpxFetcher, WebPageIngester

__all__ = [
    "DEFAULT_DATA_DIR",
    "DocumentDraft",
    "DocumentKind",
    "FetchCache",
    "Fetcher",
    "HttpxFetcher",
    "IngestError",
    "Ingester",
    "TokenBucket",
    "TranscriptIngester",
    "UploadIngester",
    "WebPageIngester",
    "data_dir",
    "default_ingesters",
    "pick",
    "strip_timestamps",
]


def default_ingesters(fetcher: Fetcher | None = None) -> list[Ingester]:
    """Transcripts first: `.txt` is claimed by both the transcript and upload ingesters."""
    return [
        TranscriptIngester(),
        WebPageIngester(fetcher if fetcher is not None else HttpxFetcher()),
        UploadIngester(),
    ]
