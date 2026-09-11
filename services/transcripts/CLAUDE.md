# sidereal-transcripts — invariants

## Invariants

- **It does not transcribe, and it never writes to Directus.** The poll loop lists and logs;
  documents stay `pending`. Choosing the transcription backend is a separate decision — do not
  stub one here.
- **Reads Directus only through `sidereal-directus`.** No direct HTTP to Directus, no Postgres.
- **Binds `SIDEREAL_TRANSCRIPTS_ADDR` (default `127.0.0.1:50051`) and nothing else** — one port.
- **A failed poll is a warning, never a crash.** Unreachable Directus, a 4xx or a decode failure
  all retry on the next tick.
- **`/healthz` is liveness only** and must not depend on Directus.
- **SIGINT and SIGTERM stop the HTTP server and the poll loop together**, through the one
  shutdown flag both watch.
