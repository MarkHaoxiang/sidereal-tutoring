# sidereal-mcp

MCP server exposing the tutoring operations to LLM agents: students, student logins, documents,
ingestion, generation, generation jobs, typesetting and the admin's view of the practice.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_DIRECTUS_TOKEN`, `SIDEREAL_TYPESET_URL`,
`SIDEREAL_DATA_DIR`, `SIDEREAL_GENERATE_BACKEND`, `SIDEREAL_GENERATE_MODEL` and
`ANTHROPIC_API_KEY`.

`SIDEREAL_DIRECTUS_TOKEN` decides what the agent can reach. A tutor's own static token acts as
that tutor and sees their students only; an administrator's token sees the whole practice and is
what the admin tools need. The bootstrap's `agent@` account is a Tutor with no students of its
own, so on a licensed instance it sees nothing until students are assigned to it.

## Tools

| | |
|---|---|
| `list_students`, `get_student`, `whoami` | Who the work is for, and who is asking. |
| `create_student_login`, `reset_student_password`, `remove_student_login` | A student's way in. |
| `list_documents`, `ingest_source` | Source material. |
| `generate_homework`, `generate_feedback`, `generate_plan` | Runs the job to completion and returns it. `generate_homework` takes `format`: `markdown` or `typst`. |
| `preview_typst` | Typst source to one SVG per page. |
| `compile_homework` | Compiles a Typst row's `content` again, replacing its PDF or setting `compile_error`. |
| `list_generation_jobs`, `update_generation_job` | The history, and a tutor's verdict on it. |
| `list_tutors`, `create_tutor`, `reset_tutor_password`, `set_tutor_status`, `remove_tutor` | The practice's tutors. Needs an administrator's token. |
| `list_jobs`, `admin_health` | Jobs across every tutor, and whether the services behind them are up. |

## Running

```sh
uv run sidereal-mcp
```

Client entry (stdio):

```json
{"command": "uv", "args": ["run", "--project", "/path/to/sidereal-tutoring", "sidereal-mcp"]}
```

```sh
uv run --package sidereal-mcp pytest packages/sidereal-mcp/tests
```
