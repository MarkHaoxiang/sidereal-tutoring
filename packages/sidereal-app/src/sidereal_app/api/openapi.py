"""Print the OpenAPI schema to stdout.

    uv run python -m sidereal_app.api.openapi > openapi.json

The frontend generates its client types from this rather than hand-writing them.
"""

from __future__ import annotations

import json

from sidereal_app.main import create_app


def main() -> None:
    print(json.dumps(create_app().openapi(), indent=2))


if __name__ == "__main__":
    main()
