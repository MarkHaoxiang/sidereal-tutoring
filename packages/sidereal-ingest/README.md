# sidereal-ingest

Turns a source into a `DocumentDraft`: transcript files (`.vtt`, `.srt`, `.txt`), web pages, tutor
uploads (`.txt`, `.pdf`, `.docx`), and handwritten pages read by a `Transcriber`.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `SIDEREAL_DATA_DIR` | `data` | Root for the fetch cache (`data/web/`). Git-ignored. |

## Usage

```python
from sidereal_ingest import default_ingesters, pick

ingesters = default_ingesters()
draft = await pick(ingesters, "https://example.org/topic").ingest("https://example.org/topic")
```

`pick` tries transcripts before uploads, so a `.txt` is read as a transcript. Call `UploadIngester()`
directly when a `.txt` is a tutor's own notes.

`create_document` and `process_document` are the Directus-facing pair: the first files a pending
`documents` row from a `FileSource`, `UrlSource`, `TextSource` or `PathSource`, the second reads it.

```python
from sidereal_ingest import TextSource, create_document, process_document

document = await create_document(client, TextSource("Factorise x^2 - 5x + 6."))
document = await process_document(client, ingesters, document.id)
```

A `ScanSource` is one or more images, or a PDF, already uploaded to Directus. `process_document`
needs the `scanner` for it; `paper_id` makes the transcription come back question by question.

```python
from sidereal_ingest import ScanIngester, ScanSource, create_document, process_document

scanner = ScanIngester(transcriber)  # `sidereal_generate.default_transcriber()` builds one
document = await create_document(client, ScanSource((file_id,), paper_id))
document = await process_document(client, ingesters, document.id, scanner=scanner)
```

```python
from sidereal_ingest import transcribe_submission

homework = await transcribe_submission(client, scanner, homework_id)
```

A PDF a tutor uploads is read layout-preserving, so stacked fractions and tables survive. When
too much of a paper is drawn rather than written, send its pages to a vision call instead, and
crop a region the model points at back out of the source.

```python
from sidereal_ingest import crop_figure, needs_page_images, page_count, page_images

if needs_page_images(content):
    images = page_images(content)  # first 40 pages; compare len() with page_count(content)
    jpeg = crop_figure(content, page=4, bbox=(0.12, 0.30, 0.88, 0.62))
```

`bbox` is `(x0, y0, x1, y1)` in 0-1 from the page's top-left, as a vision model reports it.

```sh
uv run --package sidereal-ingest pytest packages/sidereal-ingest/tests
```
