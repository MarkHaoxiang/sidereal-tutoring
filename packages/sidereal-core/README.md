# sidereal-core

Domain models and the Directus client. Every other Python package builds on these.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `SIDEREAL_DIRECTUS_URL` | `http://localhost:8055` | Directus base URL. |
| `SIDEREAL_DIRECTUS_TOKEN` | unset | Static token for service-to-service calls. |
| `SIDEREAL_TYPESET_URL` | `http://127.0.0.1:50052` | Typeset service base URL. |

## Usage

```python
from sidereal_core import Collection, DirectusClient, Student, directus_settings

settings = directus_settings()
async with DirectusClient(settings.url, settings.token) as client:
    students = await client.list_items(
        Collection.STUDENTS, Student, filter={"status": {"_eq": "active"}}, limit=50
    )
```

```python
from sidereal_core import TypesetClient, TypesetError, typeset_settings

async with TypesetClient(typeset_settings().url) as typeset:
    source = await typeset.wrap_homework(title="Week 3", student="A. Tutee", due=None, body=body)
    try:
        pdf = await typeset.compile_pdf(source)
    except TypesetError as exc:
        report = "\n".join(str(diagnostic) for diagnostic in exc.diagnostics)
```

```python
from sidereal_core.tutors import admin_health, list_tutors

async with DirectusClient(settings.url, settings.token) as client:
    tutors = await list_tutors(client)  # admin only: Directus refuses a tutor's token
```

`FakeDirectus` and `FakeTypeset` in `sidereal_core.testing` stand in for both services in tests;
`FakeDirectus(admin=True)` answers `/users/me` as an administrator.

```sh
uv run --package sidereal-core pytest packages/sidereal-core/tests
```
