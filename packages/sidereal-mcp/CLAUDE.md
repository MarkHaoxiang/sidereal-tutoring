# sidereal-mcp

Sits beside sidereal-app. Imports core, ingest and generate; never sidereal-app.

## Invariants

- Tools are thin: the body in `tools.py` is a delegation, and `server.py` is registration only. Logic
  that grows past a delegation belongs in the layer below.
- Every tool takes and returns typed values — UUIDs, `StrEnum` statuses, pydantic models — so an agent
  never parses prose.
- Tool bodies live in `tools.py` and take `Services` explicitly, so tests call them with no server.
- `Services` is constructed once per server, never per call.
- A generation tool runs the job to completion and returns the `GenerationJob`; `output_collection` and
  `output_id` say where the artefact landed.
- `ingest_source` routes on the source string and runs the same `create_document` / `process_document`
  path the app does, to completion: an unreadable source is a `failed` row, not an exception. Its
  `kind` argument only changes how the row is filed.
