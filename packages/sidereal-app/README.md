# sidereal-app

FastAPI app for the tutoring workflows. `frontend/` holds the React client.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_DATA_DIR`, `SIDEREAL_GENERATE_BACKEND`,
`SIDEREAL_GENERATE_MODEL` and `ANTHROPIC_API_KEY`. It has no Directus token of its own: every request
carries the caller's.

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
| `GET` | `/api/me` | The caller: `role` is `student` when a `students` row points at them, else `tutor`. |
| `POST` | `/api/students/{id}/login` | `{email, password}`. 201 and the new login; 409 if there is one already. |
| `POST` | `/api/students/{id}/login/password` | `{password}`. 204. |
| `DELETE` | `/api/students/{id}/login` | 204. The work stays; only the login goes. |
| `POST` | `/api/documents` | `source` is `{type: file, file_id}`, `{type: url, url}` or `{type: text, text}`. Returns 202 and the pending row. |
| `POST` | `/api/documents/{id}/process` | Reads the material again. Returns 202 and the row. |
| `POST` | `/api/jobs/{kind}` | `kind` is `homework`, `feedback` or `plan`. Returns 202 and the queued job. |
| `GET` | `/api/jobs/{id}` | The job, including `output_collection` and `output_id` once it succeeds. |

Every request but `/api/health` needs `Authorization: Bearer <directus token>`.
