# sidereal-ingest

Sits above sidereal-core. Imports core only.

## Invariants

- Every ingester is one class behind the `Ingester` protocol, producing a `DocumentDraft` and nothing else.
  No ingester touches Directus.
- `documents.py` is the one place a `documents` row is written: `create_document` files it as `pending`,
  `process_document` takes it to `ready` or `failed`.
- `process_document` never raises for a source it could not read; `error` is one plain sentence a tutor
  can act on, never a traceback or a library's wording.
- A row's `kind` is settled when it is filed and processing never changes it. A title the caller gave
  survives processing; an automatic one is marked in `metadata` until the ingester replaces it.
- A Directus file is downloaded into a temporary directory that lives only as long as the read: the
  bytes stay in Directus and the text goes in the row, so nothing is left on disk. The filename
  Directus reports is reduced to a bare name before it becomes part of a path.
- `supports()` decides routing. `source` is a filesystem path for file-backed ingesters and an http(s)
  URL for the web one.
- All outbound HTTP goes through `HttpxFetcher`: rate limited by a token bucket and cached under
  `SIDEREAL_DATA_DIR` keyed by `sha256(url)`. A cache hit costs no request and no token.
- `WebPageIngester` takes a `Fetcher`, never a URL library, so tests inject responses and never touch
  the network.
- Anything recognised but unreadable raises `IngestError`; a raw `httpx` or `OSError` never escapes.
- `.txt` is claimed by both the transcript and upload ingesters. `default_ingesters()` orders transcripts
  first; that order is the tie-break.
