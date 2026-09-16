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

```python
from sidereal_generate import paper_worksheet, rerender_paper

job = await run_job(directus, generators, job_id, typeset=typeset)  # kind `paper_extract`
paper = await rerender_paper(directus, typeset, paper_id)  # after a tutor's review edit
worksheet = await paper_worksheet(directus, typeset, paper_id, ["1", "4"], student_id=student.id)
```

A `paper_extract` job takes one document id and no student: it writes a `papers` row from the
document's text, renders the paper and its mark scheme, and files one `questions` row per
question.

`JobInput(format="typst")` makes a homework job produce a Typst source and a compiled PDF instead of
markdown; `recompile_homework(directus, typeset, id)` compiles an existing row's `content` again.

`FakeGenerator(output)` and `FailingGenerator(error)` stand in for any generator in tests.

```sh
uv run --package sidereal-generate pytest packages/sidereal-generate/tests
```
