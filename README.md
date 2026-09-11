# sidereal-tutoring

An app that assists private tutors. Directus on Postgres is the system of record — students,
sessions, ingested source material and generated artefacts (homework, feedback, plans) are all
Directus collections. Python ingests sources and generates artefacts; Rust runs the
long-running services; a React client covers the tutoring workflows and an MCP server exposes
the same operations to LLM agents.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python >= 3.12)
- [rustup](https://rustup.rs), if you are touching `crates/` or `services/`
- Node 22, if you are touching the frontend or the Directus extensions
- Docker, for the Postgres + Directus stack

## Getting running

```sh
cp .env.example .env
docker compose up -d
./scripts/directus-schema-apply.sh            # collections, fields, relations
./scripts/directus-bootstrap.sh               # Tutor role + agent token -> paste into .env
```

```sh
uv sync
```

```sh
cd packages/sidereal-app/frontend && npm install && npm run dev
```

Directus is at http://localhost:8055, the frontend at http://localhost:5173.

Everything else — running the API and the MCP server, the environment variables, the checks,
and how the schema round-trips — is in the [development guide](docs/development.md). The data
flow and who talks to whom are in [docs/architecture.md](docs/architecture.md).
