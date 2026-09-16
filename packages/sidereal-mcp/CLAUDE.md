# sidereal-mcp

Sits beside sidereal-app. Imports core, ingest and generate; never sidereal-app.

## Invariants

- Tools are thin: the body in `tools.py` is a delegation, and `server.py` is registration only. Logic
  that grows past a delegation belongs in the layer below.
- Every tool takes and returns typed values — UUIDs, `StrEnum` statuses, pydantic models — so an agent
  never parses prose.
- Tool bodies live in `tools.py` and take `Services` explicitly, so tests call them with no server.
- Over HTTP the request's `Authorization: Bearer` is the only identity: every tool builds its
  `Services` from that token, and `SIDEREAL_DIRECTUS_TOKEN` is never consulted. Stdio is the
  other way round — the environment's token is the one caller.
- The connection pool, ingesters, generators and typeset client are per process; only the
  `DirectusClient` carrying a caller's token is per request.
- A generation tool runs the job to completion and returns the `GenerationJob`; `output_collection` and
  `output_id` say where the artefact landed.
- `format` is on `generate_homework` alone: feedback and plans take no format, so `typst` cannot reach
  a job of the wrong kind.
- The admin tools carry no gate of their own: Directus refuses them for a token that is not an
  administrator's, and the server's token usually is not one.
- A tool that writes against a student calls `visible_student` first: Directus cannot check a create
  through a relation, so nothing else keeps one tutor's work out of another's student.
- `extract_paper` runs its job to completion like the other generation tools; `render_paper` and
  `paper_worksheet` call the same `sidereal_generate.papers` functions the app's endpoints do.
- `ingest_source` routes on the source string and runs the same `create_document` / `process_document`
  path the app does, to completion: an unreadable source is a `failed` row, not an exception. Its
  `kind` argument only changes how the row is filed.
