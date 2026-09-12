# sidereal-app

FastAPI app for the tutoring workflows. `frontend/` holds the React client.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_TYPESET_URL`, `SIDEREAL_DATA_DIR`,
`SIDEREAL_GENERATE_BACKEND`, `SIDEREAL_GENERATE_MODEL` and `ANTHROPIC_API_KEY`. It has no Directus
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
| `GET` | `/api/me` | The caller: `role` is `admin` when a policy grants admin access, `student` when a `students` row points at them, else `tutor`. |
| `GET` | `/api/admin/health` | Admins only. Directus, the API, typeset, the generation backend and the practice's counts. |
| `GET` | `/api/admin/tutors` | Admins only. Every tutor, with how many students they hold. |
| `POST` | `/api/admin/tutors` | `{email, password, first_name?, last_name?}`. 201 and the new tutor. |
| `POST` | `/api/admin/tutors/{user_id}/password` | `{password}`. 204. |
| `PATCH` | `/api/admin/tutors/{user_id}` | `{status}`: `active` or `suspended`. |
| `DELETE` | `/api/admin/tutors/{user_id}` | 204, or 409 `tutor_has_students` when they still hold students. |
| `GET` | `/api/admin/jobs` | `?status=&limit=`. Jobs across every tutor, with the student's name and their tutor's email. |
| `POST` | `/api/students/{id}/login` | `{email, password}`. 201 and the new login; 409 if there is one already. |
| `POST` | `/api/students/{id}/login/password` | `{password}`. 204. |
| `DELETE` | `/api/students/{id}/login` | 204. The work stays; only the login goes. |
| `POST` | `/api/documents` | `source` is `{type: file, file_id}`, `{type: url, url}` or `{type: text, text}`. Returns 202 and the pending row. |
| `POST` | `/api/documents/{id}/process` | Reads the material again. Returns 202 and the row. |
| `POST` | `/api/jobs/{kind}` | `kind` is `homework`, `feedback` or `plan`. `format` is `markdown` or `typst` and only homework takes `typst`. Returns 202 and the queued job. |
| `GET` | `/api/jobs/{id}` | The job, including `output_collection` and `output_id` once it succeeds. |
| `POST` | `/api/typeset/preview` | `{source}`. Tutors only. 200 and `{pages: [svg]}`, or 422 with `diagnostics`. |
| `POST` | `/api/homework/{id}/compile` | Tutors only. Compiles the row's `content` and returns 202 and the row; a failure sets `compile_error` and keeps the old `pdf`. |

Every request but `/api/health` needs `Authorization: Bearer <directus token>`.
