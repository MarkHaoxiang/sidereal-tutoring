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
- The `Transcriber` protocol is here and the model call is not: an implementation lives in
  sidereal-generate, and `ScanIngester` is given one.
- `ScanIngester` takes bytes, not a path: a scan's pages are rasterised and downsized in memory and
  never reach the disk. At most 20 pages, 150 dpi, 1600px on the long edge, JPEG.
- `pdf.py` is the only place a PDF is opened, and every constant that shapes one lives there.
- A PDF's text is rebuilt from per-character loose boxes into rows and columns, so stacked
  fractions, superscripts and tables keep their arrangement. Never the plain text API.
- A paper's pages go to a vision call at 110 dpi, at most 40 pages, 1400px on the long edge, JPEG —
  a scan's 150 dpi / 20 pages / 1600px is a different job and stays its own. A longer PDF is
  truncated, never refused; `page_count` is how a caller learns it was.
- `needs_page_images` is the one test of whether a paper is too drawn to read as text: images on
  at least 20% of its pages.
- A figure `bbox` is `(x0, y0, x1, y1)` normalised 0-1 from the page's top-left, and is cropped
  from a 200 dpi render of that one page. A box a model gives is clamped, unswapped and, if it
  has no area, refused.
- A figure box snaps to the drawn objects it overlaps: images if any overlap, else paths.
- A path crossing the page, whole or as a hairline, is furniture and is never a figure.
- A box with nothing drawn under it keeps its own edges, less any band of text against them, and
  is never trimmed to nothing.
- A figure's `width_mm` is its width on the source page, floored so it cannot round to nothing
  and capped at the text column.
- A scan's pages are `document_pages` rows written in order when the row is filed; processing reads
  them back by `sort` and transcribes them in that order.
- `documents.transcription` is `{questions: [...]}` and is written only when the scan names a paper.
  A notes scan's transcription is the row's `text`, and its `transcription` stays null.
- A hand-in's questions come from `sidereal_core.homework.ordered_questions`; ingest only maps
  them onto `PaperQuestion`.
- `homework.submission_transcription` is `{text, confidence, questions, model, usage}` — the whole
  transcription in the one column. Transcribing never writes `generated_from`: a student may write
  their own submission fields and Directus refuses them that one.
- A scan's `IngestError` sentences are already the tutor's: `process_document` files them as `error`
  unchanged, where every other source's are rephrased.
- `.txt` is claimed by both the transcript and upload ingesters. `default_ingesters()` orders transcripts
  first; that order is the tie-break.
