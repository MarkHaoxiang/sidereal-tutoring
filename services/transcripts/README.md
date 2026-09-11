# sidereal-transcripts

Reports the `documents` waiting to become transcripts. **It does not transcribe** — no
transcription backend has been chosen, so it never changes a document's status.

```sh
SIDEREAL_DIRECTUS_URL=http://localhost:8055 \
SIDEREAL_DIRECTUS_TOKEN=… \
cargo run -p sidereal-transcripts
```

| Variable | Default | |
| --- | --- | --- |
| `SIDEREAL_TRANSCRIPTS_ADDR` | `127.0.0.1:50051` | listen address |
| `SIDEREAL_TRANSCRIPTS_POLL_SECS` | `30` | seconds between polls |
| `SIDEREAL_DIRECTUS_URL` | required | Directus root |
| `SIDEREAL_DIRECTUS_TOKEN` | required | Directus static token |
| `RUST_LOG` | `info` | log filter |

`GET /healthz` answers `200 ok` while the process is up. It says nothing about Directus: an
unreachable Directus is logged each tick and the service keeps running. SIGINT or SIGTERM stops
the server and the poll loop.

```sh
cargo test -p sidereal-transcripts
```
