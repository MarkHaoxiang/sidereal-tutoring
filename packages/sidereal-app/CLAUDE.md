# sidereal-app

Top layer. Imports core, ingest and generate; never sidereal-mcp.

## Invariants

- The app holds no Directus credentials. Every request's own bearer token builds the `DirectusClient`,
  and `/users/me` is what validates it.
- Directus unreachable is 503, a Directus rejection is 401, and both bodies are
  `{"code", "message"}` — a client branches on `code`, never on a sentence.
- `/api/health` never touches Directus, so it still answers while Directus is down.
- One `httpx.AsyncClient` for the process, opened by the lifespan. A background job outlives its
  request, so the pool must outlive the request too.
- A job endpoint returns 202 with the queued row and runs the generation in the background. The job row,
  not the response, carries the outcome.
- Tests override `get_http_client` and `get_generators` only: the auth dependency itself is exercised,
  never stubbed.
