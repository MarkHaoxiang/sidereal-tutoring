# sidereal-core

Domain models and the Directus client. Every other Python package builds on these.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `SIDEREAL_DIRECTUS_URL` | `http://localhost:8055` | Directus base URL. |
| `SIDEREAL_DIRECTUS_TOKEN` | unset | Static token for service-to-service calls. |

## Usage

```python
from sidereal_core import Collection, DirectusClient, Student, directus_settings

settings = directus_settings()
async with DirectusClient(settings.url, settings.token) as client:
    students = await client.list_items(
        Collection.STUDENTS, Student, filter={"status": {"_eq": "active"}}, limit=50
    )
```

```sh
uv run --package sidereal-core pytest packages/sidereal-core/tests
```
