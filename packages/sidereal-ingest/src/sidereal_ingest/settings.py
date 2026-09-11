from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

DEFAULT_DATA_DIR = "data"


def data_dir(env: Mapping[str, str] | None = None) -> Path:
    """Where fetched material is cached. Git-ignored; never committed."""
    source = os.environ if env is None else env
    return Path(source.get("SIDEREAL_DATA_DIR", DEFAULT_DATA_DIR))
