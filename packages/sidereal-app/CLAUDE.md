# sidereal-app

Top layer. Imports core, ingest and generate; never sidereal-mcp.

## Invariants

- The app holds no Directus credentials. Every request's own bearer token builds the `DirectusClient`,
  and `/users/me` is what validates it. `POST /api/auth/status` is the one exception and the reason
  the app has a `SIDEREAL_DIRECTUS_TOKEN` at all: nobody refused at sign-in has a token to send.
- Directus unreachable is 503 and a Directus rejection passes on Directus's own status.
- Every non-2xx body has a `detail`: a `{"code", "message"}` object for the app's own errors, and
  FastAPI's own list for a 422. A client branches on `code`, never on a sentence.
- `/api/health` never touches Directus, so it still answers while Directus is down.
- Two `httpx.AsyncClient`s for the process, opened by the lifespan: one for Directus, one for fetching
  material. A background task outlives its request, so both pools must outlive it too.
- The ingesters are built once by the lifespan, so the web fetcher's rate limit and cache are per
  process rather than per request.
- The generators are built once by the lifespan too: the generation backend's SDK client, and the
  connection pool inside it, are per process rather than per request.
- A job endpoint returns 202 with the queued row and runs the generation in the background. The job row,
  not the response, carries the outcome.
- `POST /api/documents` returns 202 with the pending row and reads the material in the background; the
  row carries the outcome. Filing and reading the row are `sidereal_ingest.documents`, not app logic.
- The login endpoints hold no logic: `sidereal_core.logins` does the work, and a
  `StudentLoginError` becomes a status and a `code` in `main.py`, nowhere else.
- Tests override `get_http_client`, `get_generators`, `get_ingesters`, `get_scanner` and
  `get_typeset` only: the auth dependency itself is exercised, never stubbed.
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
- `POST /api/typeset/render` reads nothing and stores nothing: a canonical structure or a
  markup fragment goes in, SVG pages or the rendered source come back.
- A render's `assets` ride the request as base64 under the name a `figure` block asked for; the
  app decodes them and the core client owns both the encoding and the caps.
- An asset set over those caps is 413 `typeset_too_large`, never `typeset_failed`; a value that
  is not base64 is 422 `asset_unreadable` before any call goes out.
- `POST /api/auth/status` answers `active`, `suspended` or `unknown` and nothing more, because
  Directus returns the same `INVALID_CREDENTIALS` for a suspended account as for a wrong password.
  `unknown` does tell an unauthenticated caller that an address is not registered; a per-IP token
  bucket is what keeps that from being a way to walk an address book, and the key is
  `request.client.host`, so a deployment behind a proxy must supply the forwarded address or every
  caller shares one bucket. No service token is 503 `service_token_missing`; over the limit is 429
  `too_many_checks`.
- Archive, unarchive and delete on a student are `require_tutor`: a student is 403 `tutor_only`
  even on their own row.
- Deleting any Directus user hands that user's uploads to the caller first — the admin for a tutor,
  the tutor for a student's login — so no material is left with an owner nobody can be.
- `GET /api/me` is 403 `login_unlinked` for a Student-role login no student row points at, and so
  is every route behind `require_tutor`: the reading they share is what refuses.
- `POST /api/jobs/feedback` takes `homework_ids`; every other kind carrying them is 422
  `homework_unsupported` before a job row exists.
- `POST /api/jobs/{id}/retry` answers 202 with a new queued row and runs it in the background. The
  job that failed is left as it stands.
- A retry of a job whose student has been deleted is 422 `student_gone`, and no row is written: a
  Directus foreign key is never what a tutor reads.
- `POST /api/jobs/paper_extract` takes exactly one document and no student; every other kind takes a
  student. Both are 422 with a `code` before a job row exists.
- `pages` is on `paper_extract` alone: any other kind carrying it, even `false`, is 422
  `pages_unsupported` before a job row exists.
- Papers are the tutor's: render, worksheet and re-extracting a mark scheme are `require_tutor`, and
  each reads the paper with the caller's own token first, so a paper they cannot see is Directus's
  own answer.
- `POST /api/papers/{id}/extract_mark_scheme` reads the named document against the stored structure:
  the paper's structure, questions and rendered PDF are left as they are.
- A `PaperError` or a `GenerationError` reaching a response is 422 `paper_unusable`, carrying the
  sentence generate wrote — except `GenerationNotConfiguredError`, which is 503
  `generation_not_configured`: a missing key is an administrator's problem, not a bad paper.
- A `DocumentError` or an `IngestError` that reaches a response is 422 `material_unusable`, carrying
  the sentence ingest wrote.
- A scan is a document source like any other: `POST /api/documents` files the pages and transcribes
  them in the background, and the row carries the outcome.
- `POST /api/homework/{id}/transcribe` transcribes before it answers, and its 200 body is the row it
  wrote. The tutor may call it, and so may the student the homework belongs to; any other student is
  403 `tutor_only`.
- The scanner is built once by the lifespan, like the generators: it holds the transcription
  backend's client.
