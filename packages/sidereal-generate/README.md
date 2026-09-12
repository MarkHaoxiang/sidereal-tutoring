# sidereal-generate

Generates homework, feedback and study plans from a student and their documents.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `SIDEREAL_GENERATE_BACKEND` | `claude` | `claude` calls Anthropic; `fake` calls nothing and returns `[fake]` artefacts. |
| `SIDEREAL_GENERATE_MODEL` | `claude-sonnet-5` | Model id for every generator. |
| `SIDEREAL_GENERATE_MAX_TOKENS` | `8000` | Output cap per request. |
| `ANTHROPIC_API_KEY` | unset | Read by the Anthropic SDK on first call. |
| `SIDEREAL_TYPESET_URL` | `http://127.0.0.1:50052` | Where Typst homework is compiled. |

## Usage

```python
from sidereal_generate import GenerationRequest, homework_generator

homework = await homework_generator().generate(
    GenerationRequest(student=student, documents=(document,), instructions="Six questions.")
)
```

`JobInput(format="typst")` makes a homework job produce a Typst source and a compiled PDF instead of
markdown; `recompile_homework(directus, typeset, id)` compiles an existing row's `content` again.

`FakeGenerator(output)` and `FailingGenerator(error)` stand in for any generator in tests.

```sh
uv run --package sidereal-generate pytest packages/sidereal-generate/tests
```
