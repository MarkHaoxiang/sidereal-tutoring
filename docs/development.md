# Development guide

For humans. The `CLAUDE.md` files are written for agents and carry the invariants; this page is
how to get the thing running and how not to trip over it.

## Setup

```sh
uv sync                                              # Python workspace, all packages
uv run pre-commit install                            # ruff + mypy + cargo + shellcheck on commit
cd packages/sidereal-app/frontend && npm install
```

uv and Docker are the hard prerequisites. Node 22 is needed only for the frontend and the
Directus extensions; [rustup](https://rustup.rs) only for `crates/` and `services/` —
`rust-toolchain.toml` pins the compiler and rustup fetches it on the first `cargo` command.

The two workspaces are independent: `uv sync` never builds Rust, and cargo never reads
`pyproject.toml`. They share nothing but the `SIDEREAL_DIRECTUS_*` variables and the Directus
they both talk to.

## Running the stack

Directus is the system of record, so it comes up first. From the repo root:

```sh
cp .env.example .env
docker compose up -d
```

Postgres is `pgvector/pgvector:pg17`; Directus is pinned to `12.3.1` in `docker-compose.yml`.
Wait for both to be healthy (`docker compose ps`), then load the schema and mint the token:

```sh
./scripts/directus-schema-apply.sh   # directus/schema/snapshot.yaml -> the running instance
./scripts/directus-bootstrap.sh      # Tutor role, policy, permissions, agent service account
```

`directus-bootstrap.sh` prints a `SIDEREAL_DIRECTUS_TOKEN=` line for
`agent@sidereal.example.com`; paste the value into `.env`. It is idempotent, but Directus
conceals a static token once created, so a plain re-run cannot reprint it — use
`./scripts/directus-bootstrap.sh --rotate-token` to issue a fresh one.

The admin app is at **http://localhost:8055**, signed into with `ADMIN_EMAIL` /
`ADMIN_PASSWORD`. That is the tutor's admin surface, not a developer-only tool.

Then, one process per terminal, as you need them:

```sh
uv run uvicorn sidereal_app.main:app --reload --port 8000    # the API
cd packages/sidereal-app/frontend && npm run dev             # the client, on :5173
uv run sidereal-mcp                                          # the MCP server, on stdio
cargo run -p sidereal-transcripts                            # the transcripts service
```

Open **http://localhost:5173**. Vite proxies `/api` to port 8000, so the frontend is the only
tab you need — but the API has to be up or every job request fails. The frontend talks to
Directus directly for reads and writes, so Directus has to be up for anything to render.

`uv run sidereal-mcp` speaks stdio and is meant to be launched by a client, not by you; the
client entry is in `packages/sidereal-mcp/README.md`. `cargo run -p sidereal-transcripts`
needs `SIDEREAL_DIRECTUS_URL` and `SIDEREAL_DIRECTUS_TOKEN` in its environment, and reports
the `documents` waiting to become transcripts — **it does not transcribe**, and never writes
to Directus.

## Environment

`.env` is read by `docker compose` and by `scripts/directus-bootstrap.sh`. It is **not** loaded
by uv or cargo: export what a process needs, or prefix the command
(`set -a; . ./.env; set +a`).

### The compose stack

| Variable | Read by | |
| --- | --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | postgres | Created on first boot; baked into the volume thereafter. |
| `POSTGRES_PORT` | compose | Host port for Postgres; `5432` in the example. |
| `DB_CLIENT`, `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD` | directus | How Directus reaches that Postgres, from inside the network. |
| `KEY`, `SECRET` | directus | Dev placeholders. Anything deployed needs real random values. |
| `PUBLIC_URL` | directus | The URL Directus writes into links it generates. |
| `LOG_LEVEL` | directus | `info` in the example. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | directus, bootstrap | The admin created on first boot; the bootstrap script logs in as it. |
| `CORS_ENABLED`, `CORS_ORIGIN`, `CORS_CREDENTIALS` | directus | The browser client calls Directus directly, so the Vite origin must be allowed. |

Every one of these is required: `docker-compose.yml` declares `.env` as `required: true` and
the stack will not start without it. All of the values in `.env.example` are placeholders, and
the stack is meant to be reachable from localhost only.

### The application

| Variable | Unset | |
| --- | --- | --- |
| `SIDEREAL_DIRECTUS_URL` | `http://localhost:8055` | Directus base URL, for every Python package and Rust service. |
| `SIDEREAL_DIRECTUS_TOKEN` | no `Authorization` header is sent, so Directus applies public permissions and rejects the call as a `DirectusError` | The agent's static token. Used by `sidereal-mcp` and the Rust services; **`sidereal-app` never reads it** — it builds its client from the caller's own bearer token. |
| `SIDEREAL_DATA_DIR` | `data` | Root of the ingest fetch cache (`data/web/`). Git-ignored. |
| `SIDEREAL_GENERATE_MODEL` | `claude-sonnet-5` | Model id for every generator. Configuration, not a commit. |
| `SIDEREAL_GENERATE_MAX_TOKENS` | `8000` | Output cap per generation request. Not in `.env.example`. |
| `ANTHROPIC_API_KEY` | `POST /api/jobs/{kind}` still returns 202 and the background job lands in `failed`, its `error` column reading `TypeError: Could not resolve authentication method…`. Nothing else is affected: health, auth, ingestion and reading jobs all work. | Read by the Anthropic SDK, which is built on the first `generate()` and never at import — so the packages load and the tests pass with no key set. |
| `SIDEREAL_TRANSCRIPTS_ADDR` | `127.0.0.1:50051` | Bind address of the transcripts service. Ports are allocated in `services/README.md`, one per service. |
| `SIDEREAL_TRANSCRIPTS_POLL_SECS` | `30` | Seconds between polls. |
| `RUST_LOG` | `info` | Log filter for the Rust services. Not in `.env.example`. |

A Rust service treats `SIDEREAL_DIRECTUS_URL` and `SIDEREAL_DIRECTUS_TOKEN` as **required** and
exits with a `ConfigError` naming the variable if either is missing; an empty string counts as
missing. The Python side treats both as optional and falls back as above.

Two more live in `packages/sidereal-app/frontend`, not in the root `.env`:

| Variable | Unset | |
| --- | --- | --- |
| `VITE_DIRECTUS_URL` | `http://localhost:8055` | Where the browser reaches Directus. In `frontend/.env`, copied from `frontend/.env.example`; inlined into the bundle at build time. |
| `SIDEREAL_API_PROXY` | `http://localhost:8000` | Where `vite dev`/`vite preview` proxy `/api`. Dev-server only, deliberately not `VITE_`-prefixed. |

## Checks

```sh
uv run ruff check
uv run ruff format
uv run mypy
./run_tests.sh
```

**Run these from the repo root.** From inside `frontend/` they will appear to pass while
checking nothing. `uv run mypy` is deliberately bare: `files` in `pyproject.toml` decides the
target set, and naming packages on the command line quietly narrows it.

`./run_tests.sh` covers both workspaces: pytest per Python package, then
`cargo test --workspace`. `SIDEREAL_SKIP_RUST=1` skips the cargo half, which CI's `tests` job
sets so it does not duplicate the dedicated `rust` job; a human should not normally set it,
because it means Rust goes untested. Nothing in either suite touches the network, and all of it
passes with no credentials set anywhere — keep it that way.

For Rust, run what CI runs:

```sh
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

`--all-targets` matters: without it a warning that only appears in a test compiles clean here
and fails there.

For the frontend, from `packages/sidereal-app/frontend`:

```sh
npm run lint
npm run build          # tsc -b && vite build
```

And for the Directus extensions, from `directus/extensions`:

```sh
npm run build          # each extension -> dist/, loaded from the bind mount
npm run typecheck
npm run dev            # rebuild on change; the container reloads via EXTENSIONS_AUTO_RELOAD
```

## Things that will bite you

**The schema round-trips; it is never hand-edited.** `directus/schema/snapshot.yaml` is the
source of truth, and it moves in exactly two directions:

```sh
./scripts/directus-schema-apply.sh                  # snapshot -> running instance
./scripts/directus-schema-snapshot.sh               # running instance -> snapshot
./scripts/directus-schema-snapshot.sh /tmp/x.yaml   # ... or anywhere else
```

Edit in the admin app and snapshot immediately, or edit the file and apply — either way the
commit carries the file exactly as `directus schema snapshot` emits it. An admin-app change
that is not snapshotted is lost on the next apply, and a hand-edit that Directus would
normalise differently makes the next round-trip a spurious diff. CI applies the committed
snapshot to a fresh Directus, snapshots it back, and diffs — so a hand-edit fails there.

**Snapshots carry collections, fields and relations only.** Roles, policies, permissions and the
`agent@sidereal.example.com` service account are not in them; they live in
`scripts/directus-bootstrap.sh` and exist only once you have run it.

**The domain vocabulary is one thing in three places.** Collection names, field names and the
lowercase status/kind tokens must agree across `directus/schema/snapshot.yaml`, the
`sidereal_core` models, and `packages/sidereal-app/frontend/src/lib/schema.ts`. Nothing checks
this for you; change all three in the same commit.

**Regenerate the API client after any backend change.** Route signatures, pydantic models and
even docstrings flow into the TypeScript types:

```sh
cd packages/sidereal-app/frontend && npm run gen-api
```

It shells into `uv run python -m sidereal_app.api.openapi`, so it needs the Python workspace
installed as well as node, and it needs nothing running — the schema comes from the app object,
not from a server. It writes `openapi.json` and `src/lib/api-schema.d.ts`, both committed on
purpose, so drift shows up as a diff in review; CI regenerates and diffs them. Never hand-write a
TypeScript type to mirror a pydantic model — types flow pydantic → OpenAPI → TypeScript, one
direction only. The Directus-side types in `src/lib/schema.ts` are the exception: they mirror
the snapshot, and they are written by hand because Directus is not the app's OpenAPI.

**`sidereal-app` holds no Directus credentials.** Every request's own bearer token builds its
`DirectusClient`, and `/users/me` is what validates it. If you are poking the API with curl,
send the tutor's or the agent's token; there is no ambient authority to fall back on.

**A generation failure is a row, not an exception.** `POST /api/jobs/{kind}` answers 202 and
runs in the background; the `generation_jobs` row carries `status`, `error`, `model` and where
the artefact landed. Look there, not at the HTTP response, when a generation did not produce
what you expected.

**`data/` is git-ignored and stays that way.** Everything fetched is rate-limited and cached
there, keyed by URL hash; a cache hit costs no request.

## Where to look next

| | |
| --- | --- |
| `docs/architecture.md` | The data flow, who talks to whom, the collections |
| `directus/README.md`, `directus/CLAUDE.md` | The stack, the schema workflow, the extensions |
| `packages/*/README.md`, `packages/*/CLAUDE.md` | Per-package usage and invariants |
| `crates/*/CLAUDE.md`, `services/README.md` | The Rust libraries and the port allocation |
