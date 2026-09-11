from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from sidereal_core.models import DocumentDraft, DocumentKind


class IngestError(Exception):
    """A source we recognised but could not turn into text.

    `status` is the HTTP status when a fetch is what failed, so a caller can say which.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@runtime_checkable
class Ingester(Protocol):
    """One source kind in, one `DocumentDraft` out.

    `source` is a filesystem path for file-backed ingesters and a URL for the web one;
    `supports` is what decides which.
    """

    kind: DocumentKind

    def supports(self, source: str) -> bool: ...

    async def ingest(self, source: str) -> DocumentDraft: ...


def pick(ingesters: Sequence[Ingester], source: str) -> Ingester:
    for ingester in ingesters:
        if ingester.supports(source):
            return ingester
    raise IngestError(f"no ingester accepts {source!r}")
