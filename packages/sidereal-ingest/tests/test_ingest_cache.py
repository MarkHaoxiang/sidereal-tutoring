from __future__ import annotations

import hashlib
from pathlib import Path

from sidereal_ingest.cache import FetchCache
from sidereal_ingest.settings import DEFAULT_DATA_DIR, data_dir

URL = "https://example.test/page?a=1"


def test_key_is_the_sha256_of_the_url(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path)

    digest = hashlib.sha256(URL.encode("utf-8")).hexdigest()
    assert cache.path_for(URL) == tmp_path / f"{digest}.html"


def test_round_trip_creates_the_directory(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path / "nested" / "web")

    assert cache.read(URL) is None
    cache.write(URL, "<p>body</p>")
    assert cache.read(URL) == "<p>body</p>"


def test_data_dir_defaults_and_overrides() -> None:
    assert data_dir({}) == Path(DEFAULT_DATA_DIR)
    assert data_dir({"SIDEREAL_DATA_DIR": "/var/sidereal"}) == Path("/var/sidereal")
