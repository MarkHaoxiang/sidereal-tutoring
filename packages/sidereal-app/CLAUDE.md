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
- Tests override `get_http_client`, `get_generators` and `get_ingesters` only: the auth dependency
  itself is exercised, never stubbed.
