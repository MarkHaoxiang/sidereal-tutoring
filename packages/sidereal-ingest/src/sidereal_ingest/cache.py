from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FetchCache:
    """Fetched bodies on disk under `data/`, keyed by sha256 of the URL."""

    root: Path

    def path_for(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.html"

    def read(self, url: str) -> str | None:
        path = self.path_for(url)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, url: str, body: str) -> None:
        path = self.path_for(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
