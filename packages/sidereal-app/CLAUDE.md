# sidereal-app

Top layer. Imports core, ingest and generate; never sidereal-mcp.

## Invariants

- The app holds no Directus credentials. Every request's own bearer token builds the `DirectusClient`,
  and `/users/me` is what validates it.
- Directus unreachable is 503 and a Directus rejection passes on Directus's own status.
- Every non-2xx body has a `detail`: a `{"code", "message"}` object for the app's own errors, and
  FastAPI's own list for a 422. A client branches on `code`, never on a sentence.
- `/api/health` never touches Directus, so it still answers while Directus is down.
- Two `httpx.AsyncClient`s for the process, opened by the lifespan: one for Directus, one for fetching
  material. A background task outlives its request, so both pools must outlive it too.
- The ingesters are built once by the lifespan, so the web fetcher's rate limit and cache are per
  process rather than per request.
- A job endpoint returns 202 with the queued row and runs the generation in the background. The job row,
  not the response, carries the outcome.
- `POST /api/documents` returns 202 with the pending row and reads the material in the background; the
  row carries the outcome. Filing and reading the row are `sidereal_ingest.documents`, not app logic.
- The login endpoints hold no logic: `sidereal_core.logins` does the work, and a
  `StudentLoginError` becomes a status and a `code` in `main.py`, nowhere else.
- Tests override `get_http_client`, `get_generators`, `get_ingesters` and `get_typeset` only: the auth
  dependency itself is exercised, never stubbed.
- Typesetting is the tutor's: `require_tutor` refuses a caller a `students` row points at with 403,
  and an admin passes it.
- `/api/admin/*` is `require_admin`: a tutor and a student both get 403 `admin_only`.
- `/api/me` calls a caller an admin on `GET /policies/me/globals` alone — verified on Directus
  12.3.1, where `admin_access` is on no readable row and `/server/info` carries `version` for a
  tutor too, so neither is a probe.
- Every endpoint that writes against a student reads it first with the caller's token:
  `visible_student` refuses with 404 `student_not_found`, because Directus cannot.
- The admin endpoints hold no logic: `sidereal_core.tutors` does the work, and a `TutorError` becomes
  a status and a `code` in `main.py`, nowhere else.
- `/api/admin/health` answers 200 while a service is down — a degraded service is in the body.
- The typeset service unreachable is 503 and a message that names it; source that will not compile is
  422 carrying the compiler's `diagnostics` beside the `code`.
- `POST /api/homework/{id}/compile` compiles before it answers — the 202 body is the recompiled row,
  not a queued one. A failure sets `compile_error` and leaves the existing `pdf` in place.
- One `TypesetClient` for the process, built by the lifespan over its own pool.
- `POST /api/jobs/paper_extract` takes exactly one document and no student; every other kind takes a
  student. Both are 422 with a `code` before a job row exists.
- Papers are the tutor's: render and worksheet are `require_tutor`, and each reads the paper with the
  caller's own token first, so a paper they cannot see is Directus's own answer.
- A `PaperError` is 422 `paper_unusable`, carrying the sentence generate wrote.
