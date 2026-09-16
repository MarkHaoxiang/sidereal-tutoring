# services

Deployable Rust processes. Shared libraries they build on live in `crates/` and are never deployed.

| | Port | Bind var | Does |
| --- | --- | --- | --- |
| `transcripts` | 50051 | `SIDEREAL_TRANSCRIPTS_ADDR` | reports the `documents` waiting to become transcripts |
| `typeset` | 50052 | `SIDEREAL_TYPESET_ADDR` | compiles Typst to PDF or SVG, compiler and fonts embedded |
| `sidereal-mcp` | 50053 | `SIDEREAL_MCP_ADDR` | serves the MCP tools over Streamable HTTP (Python, in `packages/`) |

**Convention: every service reads `SIDEREAL_<SERVICE>_ADDR` to bind, holds one port, and reaches data
only through Directus** — never the Postgres behind it, and never another service's store. Ports start
at 50051 and are allocated here; verify a service's against its `src/main.rs`. `SIDEREAL_DIRECTUS_URL`
and `SIDEREAL_DIRECTUS_TOKEN` are read by every service that reaches data at all — `typeset` is pure
compute and reads neither. `RUST_LOG` filters the logs.

## Running one

```sh
SIDEREAL_DIRECTUS_URL=http://localhost:8055 SIDEREAL_DIRECTUS_TOKEN=… cargo run -p sidereal-transcripts
```

Each service's own README has its environment.
