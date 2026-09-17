# sidereal-generate

Generates homework, feedback and study plans from a student and their documents.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `SIDEREAL_GENERATE_BACKEND` | `claude` | `claude` calls Anthropic, `openrouter` calls OpenRouter; `fake` calls nothing and returns `[fake]` artefacts. |
| `SIDEREAL_GENERATE_MODEL` | `claude-sonnet-5` | Model id the `claude` backend calls. |
| `SIDEREAL_GENERATE_MAX_TOKENS` | `16000` | Output cap per request. Reasoning is spent from it too. |
| `SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS` | `48000` | Output cap for a paper extraction, the longest answer asked for. The `claude` backend takes at most 21,333 of it without streaming. |
| `SIDEREAL_GENERATE_REASONING` | `low` | How much thinking an extraction or a repair asks for: `low`, `medium` or `high`. Homework, feedback and plans leave it to the model. |
| `ANTHROPIC_API_KEY` | unset | Read by the Anthropic SDK on first call. |
| `OPENROUTER_API_KEY` | unset | Read on the first call; without it a job fails with a sentence. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Where the `openrouter` backend sends requests. |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-5` | Model id the `openrouter` backend calls. |
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
paper = await rerender_paper(directus, typeset, paper_id, extractor)  # after a review edit
worksheet = await paper_worksheet(directus, typeset, paper_id, ["1", "4"], student_id=student.id)
```

A `paper_extract` job takes one or two document ids and no student: the paper, and its mark
scheme second when the tutor filed one. The paper is read in one call and the mark scheme in a
second, under the paper's own numbers and labels. It writes a `papers` row from the text, renders
the paper and its mark scheme, and files one `questions` row per question. Maths is normalised
first — inside `$...$`, a name Typst does not know becomes quoted text and `dx` becomes `dif x` —
and whatever the compiler still refuses goes back to the model with its diagnostics, each document
on its own and at most twice; what compiles is what is stored.

`JobInput(pages=True)` sends the source PDF's pages to the model as images as well as its text,
so it can read what the text layer does not carry: ruled answer lines, answer boxes, grids, and
every diagram, graph and figure. The tutor gets those figures cropped out of the PDF, filed as
Directus images, and printed in the rendered paper. The request names which of those pages carry
drawn content; a paper that comes back with no figures at all costs one further call, and
whatever that answers is taken. `pages=False` reads the text alone, and the
default decides from the PDF — a paper with images on a fifth of its pages or more gets them.
Only the `openrouter` backend can see a page image; the others answer with a sentence saying so.

Every job files what its calls cost in `generated_from.usage` — `calls`, `prompt_tokens`,
`completion_tokens`, `total_tokens`, and `reasoning_tokens`, `images`, `image_tokens` and
`cost_usd` when there were any and the backend reports them. Nothing shows it to a tutor yet.

`JobInput(format="typst")` makes a homework job produce a Typst source and a compiled PDF instead of
markdown; `recompile_homework(directus, typeset, id)` compiles an existing row's `content` again.

`default_transcriber()` reads handwriting for `sidereal_ingest.ScanIngester`. Only the `openrouter`
backend can see an image; the others answer with a sentence saying so.

```python
from sidereal_generate import default_transcriber
from sidereal_ingest import ScanIngester

scanner = ScanIngester(default_transcriber())
```

`FakeGenerator(output)` and `FailingGenerator(error)` stand in for any generator in tests, and
`sidereal_ingest.FakeTranscriber` for the transcriber.

```sh
uv run --package sidereal-generate pytest packages/sidereal-generate/tests
```
