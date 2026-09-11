# sidereal-ingest

Turns a source into a `DocumentDraft`: transcript files (`.vtt`, `.srt`, `.txt`), web pages, and tutor
uploads (`.txt`, `.pdf`, `.docx`).

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

```sh
uv run --package sidereal-ingest pytest packages/sidereal-ingest/tests
```
