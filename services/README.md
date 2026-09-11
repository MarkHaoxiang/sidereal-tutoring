# services

Deployable Rust processes. Shared libraries they build on live in `crates/` and are never deployed.

| | Port | Bind var | Does |
| --- | --- | --- | --- |
| `transcripts` | 50051 | `SIDEREAL_TRANSCRIPTS_ADDR` | reports the `documents` waiting to become transcripts |

**Convention: every service reads `SIDEREAL_<SERVICE>_ADDR` to bind, holds one port, and reaches data
only through Directus** — never the Postgres behind it, and never another service's store. Ports start
at 50051 and are allocated here; verify a service's against its `src/main.rs`. `SIDEREAL_DIRECTUS_URL`
and `SIDEREAL_DIRECTUS_TOKEN` are read by every one of them, and `RUST_LOG` filters the logs.

## Running one

```sh
SIDEREAL_DIRECTUS_URL=http://localhost:8055 SIDEREAL_DIRECTUS_TOKEN=… cargo run -p sidereal-transcripts
```

Each service's own README has its environment.
