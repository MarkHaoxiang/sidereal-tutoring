# sidereal-ingest

Sits above sidereal-core. Imports core only.

## Invariants

- Every ingester is one class behind the `Ingester` protocol, producing a `DocumentDraft` and nothing else.
  No Directus writes here; the caller persists.
- `supports()` decides routing. `source` is a filesystem path for file-backed ingesters and an http(s)
  URL for the web one.
- All outbound HTTP goes through `HttpxFetcher`: rate limited by a token bucket and cached under
  `SIDEREAL_DATA_DIR` keyed by `sha256(url)`. A cache hit costs no request and no token.
- `WebPageIngester` takes a `Fetcher`, never a URL library, so tests inject responses and never touch
  the network.
- Anything recognised but unreadable raises `IngestError`; a raw `httpx` or `OSError` never escapes.
- `.txt` is claimed by both the transcript and upload ingesters. `default_ingesters()` orders transcripts
  first; that order is the tie-break.
