# sidereal-mcp

MCP server exposing the tutoring operations to LLM agents: students, student logins, documents,
ingestion, generation, generation jobs, typesetting and the admin's view of the practice.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_DIRECTUS_TOKEN`, `SIDEREAL_TYPESET_URL`,
`SIDEREAL_DATA_DIR`, `SIDEREAL_GENERATE_BACKEND`, `SIDEREAL_GENERATE_MODEL`,
`ANTHROPIC_API_KEY` and, for the HTTP transport, `SIDEREAL_MCP_ADDR` (default
`127.0.0.1:50053`).

Over stdio, `SIDEREAL_DIRECTUS_TOKEN` decides what the agent can reach. Over HTTP each
request's own `Authorization: Bearer <token>` does, and the environment's token is never
consulted. Either way: a tutor's own static token acts as that tutor and sees their students
only; an administrator's token sees the whole practice and is what the admin tools need; a
session access token from `POST /auth/login` works wherever a static one does. The bootstrap's
`agent@` account is a Tutor with no students of its own, so on a licensed instance it sees
nothing until students are assigned to it.

## Tools

| | |
|---|---|
| `list_students`, `get_student`, `whoami` | Who the work is for, and who is asking. |
| `create_student_login`, `reset_student_password`, `remove_student_login` | A student's way in. |
| `list_documents`, `ingest_source` | Source material. |
| `generate_homework`, `generate_feedback`, `generate_plan` | Runs the job to completion and returns it. `generate_homework` takes `format`: `markdown` or `typst`. |
| `extract_paper`, `render_paper`, `paper_worksheet` | A document read into a paper (with `mark_scheme_id` when its mark scheme is a second document), its PDFs made again, and some of its questions as one worksheet. |
| `preview_typst` | Typst source to one SVG per page. |
| `compile_homework` | Compiles a Typst row's `content` again, replacing its PDF or setting `compile_error`. |
| `list_generation_jobs`, `update_generation_job` | The history, and a tutor's verdict on it. |
| `list_tutors`, `create_tutor`, `reset_tutor_password`, `set_tutor_status`, `remove_tutor` | The practice's tutors. Needs an administrator's token. |
| `list_jobs`, `admin_health` | Jobs across every tutor, and whether the services behind them are up. |

## Running

```sh
uv run sidereal-mcp          # stdio
uv run sidereal-mcp --http   # Streamable HTTP, at /mcp on SIDEREAL_MCP_ADDR
```

Setting `SIDEREAL_MCP_ADDR` serves HTTP on its own, as `--http` does. Bind `0.0.0.0:50053` to
be reachable from another machine.

## Connect Claude Code

Local, over stdio:

```sh
claude mcp add sidereal -e SIDEREAL_DIRECTUS_TOKEN=<directus token> \
  -- uv run --project /path/to/sidereal-tutoring sidereal-mcp
```

Someone else's Claude Code, over the network:

```sh
claude mcp add --transport http sidereal http://<host>:50053/mcp \
  --header "Authorization: Bearer <directus token>"
```

`claude mcp list` checks the connection, and `whoami` reports the role the token carries.
Give a tutor their own static token and the server acts as that tutor; an admin token sees
every tutor's work. Directus serves its own `/mcp` on port 8055 for raw collection access;
this server is the tutoring operations, not the tables.

```sh
uv run --package sidereal-mcp pytest packages/sidereal-mcp/tests
```
