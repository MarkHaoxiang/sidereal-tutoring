# sidereal-app

FastAPI app for the tutoring workflows. `frontend/` holds the React client.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_TYPESET_URL`, `SIDEREAL_DATA_DIR`,
`SIDEREAL_GENERATE_BACKEND`, `SIDEREAL_GENERATE_MODEL` and `ANTHROPIC_API_KEY`. Every request
carries the caller's own Directus token; `SIDEREAL_DIRECTUS_TOKEN` is used by `POST
/api/auth/status` alone, which has no caller to borrow one from.

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
| `POST` | `/api/auth/status` | No token. `{email}`. `{status}`: `active`, `suspended` or `unknown` — why a sign-in was refused, for someone who has just been refused one. Rate limited per caller. |
| `GET` | `/api/me` | The caller: `role` is `admin` when a policy grants admin access, `student` when a `students` row points at them, else `tutor`. |
| `GET` | `/api/admin/health` | Admins only. Directus, the API, typeset, the generation backend and the practice's counts. |
| `GET` | `/api/admin/tutors` | Admins only. Every tutor, with how many students they hold. |
| `POST` | `/api/admin/tutors` | `{email, password, first_name?, last_name?}`. 201 and the new tutor. |
| `POST` | `/api/admin/tutors/{user_id}/password` | `{password}`. 204. |
| `PATCH` | `/api/admin/tutors/{user_id}` | `{status}`: `active` or `suspended`. |
| `DELETE` | `/api/admin/tutors/{user_id}` | 204, or 409 `tutor_has_students` when they still hold students. |
| `GET` | `/api/admin/jobs` | `?status=&limit=`. Jobs across every tutor, with the student's name and their tutor's email. |
| `POST` | `/api/students/{id}/archive` | Tutors only. Files the student away and suspends their login. |
| `POST` | `/api/students/{id}/unarchive` | Tutors only. The reverse of both. |
| `DELETE` | `/api/students/{id}` | Tutors only, and their own student. 204. Their login, sessions, homework, feedback and plans go; their material joins the library and their jobs stay in the history. |
| `POST` | `/api/students/{id}/login` | `{email, password}`. 201 and the new login; 409 if there is one already. |
| `POST` | `/api/students/{id}/login/password` | `{password}`. 204. |
| `DELETE` | `/api/students/{id}/login` | 204. The work stays; only the login goes. |
| `POST` | `/api/documents` | `source` is `{type: file, file_id}`, `{type: url, url}`, `{type: text, text}` or `{type: scan, file_ids, paper_id?}`. Returns 202 and the pending row. |
| `POST` | `/api/documents/{id}/process` | Reads the material again. Returns 202 and the row. |
| `POST` | `/api/jobs/{kind}` | `kind` is `homework`, `feedback`, `plan` or `paper_extract`. `format` is `markdown` or `typst` and only homework takes `typst`. `homework_ids` is feedback's alone: the hand-ins the feedback is about. `paper_extract` takes one `document_ids` entry and no student, and alone takes `pages`: `true` or `false` to force sending the PDF's pages as images, `null` (default) to decide from the PDF. Returns 202 and the queued job. |
| `GET` | `/api/jobs/{id}` | The job, including `output_collection` and `output_id` once it succeeds. |
| `POST` | `/api/jobs/{id}/retry` | The same input as a new job. 202 and the new queued row; the one that failed is left alone. |
| `POST` | `/api/papers/{id}/render` | Tutors only. Renders the stored structure again and returns 202 and the row. |
| `POST` | `/api/papers/{id}/extract_mark_scheme` | Tutors only. `{document_id}`. Reads that mark scheme against the stored structure and returns 202 and the row. |
| `POST` | `/api/papers/{id}/worksheet` | Tutors only. `{question_numbers, student_id?, title?, due?}`. 200 and `{source, pdf_file_id, homework_id}`. With a `student_id` it also sets the worksheet as a draft homework and `homework_id` is that row. |
| `POST` | `/api/typeset/preview` | `{source}`. Tutors only. 200 and `{pages: [svg]}`, or 422 with `diagnostics`. |
| `POST` | `/api/homework/{id}/transcribe` | The tutor, or the student the homework belongs to. Reads `submission_file` into `submission_transcription` (`{text, confidence, questions, model, usage}`) and returns 200 and the row. |
| `POST` | `/api/homework/{id}/compile` | Tutors only. Compiles the row's `content` and returns 202 and the row; a failure sets `compile_error` and keeps the old `pdf`. |

Every request but `/api/health` needs `Authorization: Bearer <directus token>`.
