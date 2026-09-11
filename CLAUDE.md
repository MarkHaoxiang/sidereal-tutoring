# sidereal-tutoring

An app that assists private tutors. **Directus, on Postgres, is the backend and the system
of record**: students, sessions, ingested source material (video transcripts, scraped pages
and question banks, tutors' own uploads) and generated artefacts (homework, feedback, plans)
are all Directus collections. **Python ingests and generates** — `sidereal-ingest` turns a
source into a `documents` row, `sidereal-generate` turns documents plus student context into
an artefact. **Rust builds individual services** where a long-running or performance-sensitive
worker is warranted. Two audiences, always: **non-technical tutors** (clear UI, no jargon,
safe defaults) and **LLM agents** (typed, documented, idempotent operations; every state
machine explicit).

## Goals and current phase

1. **Tutors organise students, sessions and material without technical work.** Directus's own
   admin app is that surface — generic CRUD screens are not rebuilt in React.
2. **Generation is a job, not a chat.** Every run is a `generation_jobs` row carrying its
   input, model, outcome and provenance, so a tutor and an agent see the same history.
3. **Every operation the app has, an agent has.** `sidereal-mcp` is the agent surface and
   delegates to the same packages the app does; neither grows logic the other lacks.

**Current phase: scaffold complete.** Every layer exists and is tested, but **no real
ingestion or generation has run against real data yet** — the domain shapes are provisional
and should be expected to move. The compose stack is local dev only. The transcripts service
polls and logs; it does not transcribe.

Standing rules: **agents never commit the user to a cost they did not choose** — no purchases,
signups, trials or raised limits; flag them as human actions. `ANTHROPIC_API_KEY` reaches a
process through the environment only, and tests and CI run with no key set.

## Layout

- `directus/` — `schema/snapshot.yaml` (the schema, as code), `extensions/` (TypeScript),
  and the invariants in its own `CLAUDE.md`. Directus is pinned in `docker-compose.yml`.
- `packages/` — uv workspace members, layered one-way; lower layers never import higher ones:
  `sidereal-core → sidereal-ingest → sidereal-generate → sidereal-app`, with `sidereal-mcp`
  **beside** `sidereal-app` (it imports core/ingest/generate; app and mcp never import each
  other, and nothing imports either). `packages/sidereal-app/frontend/` is the React client.
  The layering is enforced by per-package `ruff.toml` banned-api entries, not by convention.
- `crates/` — shared Rust **libraries**, never deployed.
- `services/` — deployable Rust **processes**, one port each. The path answers "is this
  deployed?".
- `scripts/` — the Directus schema round-trip and the role/token bootstrap. Shellcheck-clean.
- `docs/` — `development.md` (for humans), `architecture.md` (the data flow and who talks to
  whom).
- Each package: `pyproject.toml`, `ruff.toml`, `README.md`, `CLAUDE.md`,
  `src/sidereal_<x>/`, `tests/` mirroring `src/`.
- **Documentation is deliberately concise — write only what the code cannot say.** Never
  restate what a quick scan of the code or its types already shows: no signature or field
  descriptions, no file inventories, no narration of what a function does, and no design
  rationale or decision history — not in READMEs, CLAUDE.md files, doc comments, or module
  headers. A CLAUDE.md records invariants and constraints as terse bullets — state *what must
  hold*, one line each, not why it was chosen. READMEs say how to run and use the package,
  nothing else. When editing a file whose docs violate this, trim them; do not match their
  style.

## Ways of working

- **The main agent is an orchestrator, always, unless the user specifically instructs
  otherwise.** This is the default, not a preference to weigh against convenience: if the work
  is writing code, it goes to a subagent. Not "most coding" — coding. The main session exists
  to design, brief, review, verify, and talk to the user. Reaching for Edit because a change
  looks small enough to just do is the failure mode this rule names; a task being small is an
  argument for a cheap agent, not for doing it yourself. Two carve-outs only: verification
  (below), and work the user has directly asked the main session to perform.
- **Delegation shape** — Opus for design-bearing work (architecture, tricky UI, algorithms,
  the Directus schema), Sonnet for mechanical work (CSS modules, boilerplate, config,
  straightforward CRUD). Partition tasks by file so parallel agents never write the same path,
  and give each the conventions below. Brief agents on facts you have verified; a wrong claim
  in a brief becomes wrong code, and the agent cannot tell. **Every coding agent's brief opens
  by requiring it to read this file — the Conventions section especially, documentation rules
  included — plus the CLAUDE.md of each package it will touch, before writing anything.**
- Verification stays in the main loop: run `uv run ruff check`, `uv run mypy`, `./run_tests.sh`,
  and `npm run build` after agents report; review before committing. Check the work, not the
  report — agents describe what they intended, which is not always what is on disk.

## Conventions

- Python >= 3.12, uv workspace. Add cross-package deps via `[tool.uv.sources]`
  `{ workspace = true }`.
- Checks: `uv run ruff check`, `uv run ruff format`, `uv run mypy` (strict, and bare — the
  `files` setting in `pyproject.toml` decides the target set), `./run_tests.sh`. Pre-commit
  runs ruff, mypy, cargo fmt/clippy and shellcheck.
- Tests: pytest per package, `tests/` mirroring `src/`. **Test filenames must be unique across
  the whole workspace** (mypy maps them to modules), so prefix with the package.
- Rust: edition 2024, toolchain pinned by `rust-toolchain.toml`. Every member writes
  `[lints] workspace = true`; the workspace denies `unwrap_used`, `panic`, `todo`,
  `unimplemented`, `dbg_macro`, `print_stdout`, `exit`, `float_cmp` and forbids `unsafe_code`.
  `cargo clippy --workspace --all-targets -- -D warnings` is what CI runs; run it with
  `--all-targets` locally or a test-only warning passes here and fails there.
- Every Rust service reads `SIDEREAL_<SERVICE>_ADDR` to bind, holds one port (allocated in
  `services/README.md`), and reaches data only through Directus — never the Postgres behind
  it, never another service's store.
- **The domain vocabulary is one thing in three places.** Collection names, field names and
  the lowercase status/kind tokens must agree across `directus/schema/snapshot.yaml`, the
  `sidereal_core` models, and `packages/sidereal-app/frontend/src/lib/schema.ts`. Changing one
  means changing all three in the same commit.
- **The schema snapshot is applied, never hand-edited.** Change it in the admin app and run
  `scripts/directus-schema-snapshot.sh`, or edit it and run `scripts/directus-schema-apply.sh`;
  commit it exactly as Directus emits it. Roles, policies, permissions and the agent service
  account are not in snapshots — they live in `scripts/directus-bootstrap.sh`.
- **No secrets in the tree.** `.env.example` carries dev-only placeholders and `.env` is
  git-ignored. A real key reaches a process through the environment, never a file under
  version control, a fixture or a log line.
- **Tests and CI never touch the network.** Ingest tests inject responses, generation tests use
  a fake generator, Rust tests run against a `wiremock` stub. `./run_tests.sh` must pass with
  no credentials set anywhere, and must keep doing so.
- **LLM spend**: `ANTHROPIC_API_KEY` from the environment only; the model id is configuration
  (`SIDEREAL_GENERATE_MODEL`), not a commit. An agent may not buy, subscribe to, or raise the
  limit on anything.
- Fetched material is cached under `SIDEREAL_DATA_DIR` (`data/`, git-ignored) and never
  committed. Rate-limit and cache everything that leaves the machine.
- No placeholder content that pretends to be real — no invented students, no lorem ipsum.
  Test fixtures are fine and live under `tests/`.
- No TODO/FIXME markers. Something deferred is a typed error or is left out.
