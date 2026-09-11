# sidereal-core

Bottom layer. Imports no other workspace package.

## Invariants

- No LLM calls, no scraping, no filesystem state. Directus is the only external service reached.
- Models are the shared vocabulary: Directus collections, pydantic models and the frontend's TS types
  carry the same field names and the same lowercase status tokens.
- One model per collection plus a `<Name>Draft` for creation. A `Draft` has no `id` and no audit
  fields; a record has both.
- `Draft.payload()` drops `None`: unset means "Directus decides", never "write null".
- Records are frozen and ignore unknown fields, so a Directus schema addition cannot break a read.
- m2o relations are the related row's `UUID`, not a nested object. Requesting `fields` that expand a
  relation would break validation.
- Every failure is a `DirectusClientError`: `DirectusUnavailableError` when Directus cannot be reached,
  `DirectusError` (status + Directus's `errors[]`) when it answers with one.
- Settings are a frozen dataclass over `os.environ`, read on call. No I/O at import.
- Files are Directus's own collection, not `/items`: the row comes from `/files/{id}` and the bytes
  from `/assets/{id}`. `download_file` names the bytes with the row's `filename_download`, never
  with a name parsed out of a response header.
