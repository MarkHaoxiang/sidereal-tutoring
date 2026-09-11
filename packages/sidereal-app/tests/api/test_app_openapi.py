from __future__ import annotations

import json
import subprocess
import sys


def test_the_module_prints_the_schema() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sidereal_app.api.openapi"],
        capture_output=True,
        text=True,
        check=True,
    )

    schema = json.loads(result.stdout)
    assert schema["info"]["title"] == "Sidereal Tutoring"
    assert "/api/health" in schema["paths"]
