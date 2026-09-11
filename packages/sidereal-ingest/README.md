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

```sh
uv run --package sidereal-ingest pytest packages/sidereal-ingest/tests
```
