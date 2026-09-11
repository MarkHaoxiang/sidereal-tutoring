# sidereal-mcp

MCP server exposing the tutoring operations to LLM agents: students, documents, ingestion, generation
and generation jobs.

## Configuration

Reads `SIDEREAL_DIRECTUS_URL`, `SIDEREAL_DIRECTUS_TOKEN`, `SIDEREAL_DATA_DIR`,
`SIDEREAL_GENERATE_BACKEND`, `SIDEREAL_GENERATE_MODEL` and `ANTHROPIC_API_KEY`.

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
