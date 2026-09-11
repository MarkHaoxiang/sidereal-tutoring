# sidereal-generate

Sits above sidereal-ingest. Imports core and ingest only.

## Invariants

- Every generator is one `Generator[OutputT]` implementation, so two can be compared on the same request.
- `SIDEREAL_GENERATE_BACKEND` decides what `default_generators()` builds: `claude` (default) or `fake`.
  Fake output is prefixed `[fake]` and says so in its body; it never passes as real generation.
- No network at import and none in tests. The Anthropic client is built on first `generate()`, never in
  `__init__`, so constructing a generator needs no credentials.
- Output comes back through a forced strict tool call whose `input_schema` is the output model's JSON
  schema. Every output field is required and optional ones are nullable — a strict schema has no
  optional properties.
- A reply with no tool call, or one that fails validation, raises `GenerationError`. A half-filled
  artefact is never returned.
- Prompts are module-level constants in `prompts.py`, not built at call time.
- Generators return pydantic outputs only. `jobs.py` is the one place a generated artefact is written
  back to Directus, and the one place that knows the provenance shape (`job`, `model`, `documents`).
- `run_job` never raises for a generation failure: the job row carries the outcome, so every failure is
  visible to the tutor and to an agent.
- A job's `error` is one plain sentence a tutor can act on. The exception behind it is logged at error
  level, never stored.
- A homework job writes the generated questions as `questions` rows, links each to the homework with a
  `homework_questions` row sorted from 1 in the order generated, and records their ids in
  `generated_from`.
