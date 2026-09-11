# sidereal-app

FastAPI app for the tutoring workflows. `frontend/` holds the React client.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_GENERATE_MODEL` and `ANTHROPIC_API_KEY`. It has no Directus
token of its own: every request carries the caller's.

## Running

```sh
uv run uvicorn sidereal_app.main:app --reload
uv run python -m sidereal_app.api.openapi > openapi.json
uv run --package sidereal-app pytest packages/sidereal-app/tests
```

## Endpoints

| Method | Path | |
|---|---|---|
| `GET` | `/api/health` | No token. |
| `POST` | `/api/jobs/{kind}` | `kind` is `homework`, `feedback` or `plan`. Returns 202 and the queued job. |
| `GET` | `/api/jobs/{id}` | The job, including `output_collection` and `output_id` once it succeeds. |

Every request but `/api/health` needs `Authorization: Bearer <directus token>`.
