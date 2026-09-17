#![allow(clippy::unwrap_used, clippy::panic)]

//! The service over HTTP: every endpoint, every documented failure.

use serde_json::{Value, json};
use sidereal_typeset::{MAX_SOURCE_BYTES, router};
use tokio::net::TcpListener;
use tokio::task::JoinHandle;

const MATHS: &str = "Solve for $x$:\n$ x^2 - 5 x + 6 = 0 $\nso $x = 2$ or $x = 3$.\n";

struct Service {
    base: String,
    server: JoinHandle<()>,
    client: reqwest::Client,
}

impl Service {
    async fn start() -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let server = tokio::spawn(async move {
            axum::serve(listener, router()).await.unwrap();
        });
        Self {
            base,
            server,
            client: reqwest::Client::new(),
        }
    }

    async fn post(&self, path: &str, body: Value) -> reqwest::Response {
        self.client
            .post(format!("{}{path}", self.base))
            .json(&body)
            .send()
            .await
            .unwrap()
    }
}

impl Drop for Service {
    fn drop(&mut self) {
        self.server.abort();
    }
}

#[tokio::test]
async fn healthz_answers_ok() {
    let service = Service::start().await;

    let response = reqwest::get(format!("{}/healthz", service.base))
        .await
        .unwrap();
    assert_eq!(response.status().as_u16(), 200);
    assert_eq!(response.text().await.unwrap(), "ok");

    let missing = reqwest::get(format!("{}/", service.base)).await.unwrap();
    assert_eq!(missing.status().as_u16(), 404);
}

#[tokio::test]
async fn display_maths_compiles_to_a_pdf() {
    let service = Service::start().await;

    let response = service
        .post("/compile", json!({ "source": MATHS, "output": "pdf" }))
        .await;
    assert_eq!(response.status().as_u16(), 200);
    assert_eq!(response.headers()["content-type"], "application/pdf");

    let bytes = response.bytes().await.unwrap();
    assert!(bytes.len() > 1000, "{} bytes", bytes.len());
    assert!(
        bytes.starts_with(b"%PDF"),
        "{:?}",
        &bytes[..8.min(bytes.len())]
    );
}

#[tokio::test]
async fn a_two_page_document_renders_two_svg_pages() {
    let service = Service::start().await;
    let source = format!("{MATHS}#pagebreak()\nAnd $integral_0^1 x dif x = 1/2$.\n");

    let response = service
        .post("/compile", json!({ "source": source, "output": "svg" }))
        .await;
    assert_eq!(response.status().as_u16(), 200);

    let body: Value = response.json().await.unwrap();
    let pages = body["pages"].as_array().unwrap();
    assert_eq!(pages.len(), 2);
    for page in pages {
        assert!(page.as_str().unwrap().contains("<svg"), "{page}");
    }
}

#[tokio::test]
async fn a_syntax_error_is_a_422_with_a_line_and_column() {
    let service = Service::start().await;
    let source = "First line is fine.\n\n#let broken = (1, 2\n";

    let response = service
        .post("/compile", json!({ "source": source, "output": "pdf" }))
        .await;
    assert_eq!(response.status().as_u16(), 422);

    let body: Value = response.json().await.unwrap();
    let first = &body["diagnostics"][0];
    assert_eq!(first["severity"], "error");
    assert_eq!(first["line"], 3, "{body}");
    assert!(first["column"].as_u64().unwrap() >= 1, "{body}");
    assert!(!first["message"].as_str().unwrap().is_empty(), "{body}");
}

#[tokio::test]
async fn a_package_import_is_refused_with_a_clear_message() {
    let service = Service::start().await;
    let source = "#import \"@preview/cetz:0.3.1\": canvas\n\nHello.\n";

    let response = service
        .post("/compile", json!({ "source": source, "output": "pdf" }))
        .await;
    assert_eq!(response.status().as_u16(), 422);

    let body: Value = response.json().await.unwrap();
    let first = &body["diagnostics"][0];
    let message = first["message"].as_str().unwrap();
    assert!(
        message.contains("package imports are not available"),
        "{message}"
    );
    assert!(message.contains("@preview/cetz:0.3.1"), "{message}");
    assert_eq!(first["line"], 1, "{body}");
}

#[tokio::test]
async fn an_oversize_source_is_a_413() {
    let service = Service::start().await;
    let source = "a".repeat(MAX_SOURCE_BYTES + 1);

    let response = service
        .post("/compile", json!({ "source": source, "output": "pdf" }))
        .await;
    assert_eq!(response.status().as_u16(), 413);

    let body: Value = response.json().await.unwrap();
    assert!(
        body["message"].as_str().unwrap().contains("limit"),
        "{body}"
    );
}

#[tokio::test]
async fn a_wrapped_homework_carries_the_title_and_compiles() {
    let service = Service::start().await;
    let body = "#question[Factorise $x^2 - 5x + 6$.]\n#answerlines(3)\n\
                #question[Hence solve $x^2 - 5x + 6 = 0$.]\n#answerlines(2)\n";

    let wrapped = service
        .post(
            "/template",
            json!({
                "kind": "homework",
                "title": "Quadratics, week 3",
                "student": "A. Student",
                "due": "2026-09-25",
                "body": body,
            }),
        )
        .await;
    assert_eq!(wrapped.status().as_u16(), 200);

    let source = wrapped.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(source.contains("Quadratics, week 3"), "{source}");
    assert!(source.contains("A. Student"), "{source}");
    assert!(source.contains("2026-09-25"), "{source}");
    assert!(source.contains("#let question("), "{source}");

    let compiled = service
        .post("/compile", json!({ "source": source, "output": "pdf" }))
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

#[tokio::test]
async fn a_template_kind_that_does_not_exist_is_refused() {
    let service = Service::start().await;

    let response = service
        .post(
            "/template",
            json!({ "kind": "essay", "title": "t", "body": "b" }),
        )
        .await;
    assert_eq!(response.status().as_u16(), 422);
}

fn paper() -> Value {
    json!({
        "title": "Pure Mathematics 1",
        "source": "Specimen paper",
        "board": "Edexcel",
        "year": 2025,
        "time_minutes": 90,
        "total_marks": 75,
        "instructions": "Answer *all* questions in the spaces provided.",
        "questions": [
            {
                "number": "1",
                "stem": "The curve $C$ has equation $y = x^3 - 6x^2 + 9x + 1$.",
                "parts": [
                    { "label": "a", "text": "Find $(d y) / (d x)$.", "marks": 2, "answer_lines": 3 },
                    {
                        "label": "b",
                        "text": "Hence find the stationary points of $C$.",
                        "marks": 5,
                        "answer_lines": 6,
                        "parts": [
                            { "label": "i", "text": "Determine the nature of each.", "marks": 3, "answer_lines": 4 },
                            { "label": "ii", "text": "Sketch $C$.", "marks": 2, "answer_lines": 5 },
                        ],
                    },
                ],
            },
            {
                "number": "2",
                "stem": "A geometric series has $a = 24$ and $|r| < 1$.",
                "marks": 4,
                "answer_lines": 4,
                "parts": [
                    { "label": "a", "text": "Show that $r = 1/4$.", "marks": 3, "answer_lines": 5 },
                    { "label": "b", "text": "Find $sum_(n=1)^(oo) 24 (1/4)^(n-1)$.", "marks": 4, "answer_lines": 6 },
                ],
            },
        ],
    })
}

#[tokio::test]
async fn a_paper_renders_to_a_pdf_and_to_the_source_behind_it() {
    let service = Service::start().await;

    let rendered = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": paper(), "output": "source" }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);

    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(source.contains("#paper-question(\"1\", none)["), "{source}");
    assert!(source.contains("#part(\"a\", 2)["), "{source}");
    assert!(source.contains("#subpart(\"ii\", 2)["), "{source}");
    assert!(
        source.contains("#answerlines(4, indent: part-indent * 2)"),
        "{source}"
    );
    assert!(source.contains("total-marks: 75"), "{source}");

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": paper(), "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert_eq!(compiled.headers()["content-type"], "application/pdf");
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));

    let pages = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": paper(), "output": "svg" }),
        )
        .await;
    assert_eq!(pages.status().as_u16(), 200);
    let body: Value = pages.json().await.unwrap();
    assert_eq!(body["pages"].as_array().unwrap().len(), 2, "{body}");
}

#[tokio::test]
async fn a_mark_scheme_renders_every_part_and_its_notes() {
    let service = Service::start().await;
    let document = json!({
        "title": "Pure Mathematics 1",
        "questions": [
            {
                "number": "1",
                "parts": [
                    {
                        "label": "a",
                        "answer": "$(d y) / (d x) = 3x^2 - 12x + 9$",
                        "marks": 2,
                        "notes": "M1 for any two terms correct.",
                    },
                ],
            },
            {
                "number": "2",
                "answer": "$S_oo = a / (1 - r)$",
                "notes": "Quote the formula before substituting.",
                "parts": [{ "label": "a", "answer": "$r = 1/4$", "marks": 3 }],
            },
        ],
    });

    let rendered = service
        .post(
            "/render",
            json!({ "kind": "mark_scheme", "document": document, "output": "source" }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);
    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(source.contains("#scheme-question(\"2\")["), "{source}");
    assert!(source.contains("#scheme-row(none, none)["), "{source}");
    assert!(source.contains("#scheme-row(\"a\", 3)["), "{source}");
    assert!(source.contains("#scheme-note["), "{source}");

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "mark_scheme", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

#[tokio::test]
async fn a_worksheet_carries_the_student_and_the_due_date() {
    let service = Service::start().await;
    let document = json!({
        "title": "Quadratics, week 3",
        "student": "A. Student",
        "due": "2026-09-25",
        "intro": "Show every step.",
        "questions": [
            { "number": "1", "stem": "Factorise $x^2 - 5x + 6$.", "marks": 2, "answer_lines": 3 },
            { "number": "2", "stem": "Hence solve $x^2 - 5x + 6 = 0$.", "marks": 3, "answer_lines": 4 },
        ],
    });

    let rendered = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": document, "output": "source" }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);
    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(source.contains("student: \"A. Student\""), "{source}");
    assert!(source.contains("due: \"2026-09-25\""), "{source}");
    assert!(source.contains("#paper-question(\"2\", 3)["), "{source}");

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

#[tokio::test]
async fn an_unknown_field_is_a_422_naming_the_path_to_it() {
    let service = Service::start().await;
    let document = json!({
        "title": "Pure Mathematics 1",
        "questions": [
            { "number": "1" },
            { "number": "2" },
            { "number": "3", "parts": [{ "label": "a", "text": "Find $x$.", "mark": 3 }] },
        ],
    });

    let response = service
        .post("/render", json!({ "kind": "paper", "document": document }))
        .await;
    assert_eq!(response.status().as_u16(), 422);

    let body: Value = response.json().await.unwrap();
    let first = &body["errors"][0];
    assert_eq!(first["path"], "questions[2].parts[0].mark", "{body}");
    assert!(
        first["message"].as_str().unwrap().contains("unknown field"),
        "{body}"
    );
}

#[tokio::test]
async fn a_part_that_nests_twice_is_refused() {
    let service = Service::start().await;
    let document = json!({
        "title": "Depth",
        "questions": [{
            "number": "1",
            "parts": [{
                "label": "a",
                "text": "One.",
                "parts": [{
                    "label": "i",
                    "text": "Two.",
                    "parts": [{ "label": "A", "text": "Three." }],
                }],
            }],
        }],
    });

    let response = service
        .post("/render", json!({ "kind": "paper", "document": document }))
        .await;
    assert_eq!(response.status().as_u16(), 422);

    let body: Value = response.json().await.unwrap();
    assert_eq!(
        body["errors"][0]["path"], "questions[0].parts[0].parts[0].parts",
        "{body}"
    );
}

#[tokio::test]
async fn a_bracket_or_a_hash_in_a_field_is_printed_not_obeyed() {
    let service = Service::start().await;
    let document = json!({
        "title": "Escaping",
        "questions": [{
            "number": "1",
            "stem": "Brackets and hashes",
            "parts": [{
                "label": "a",
                "text": "Take $x$ in [0, 1], tag #3, and ] #pagebreak() [ // ends it",
                "marks": 2,
            }],
        }],
    });

    let rendered = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": document, "output": "source" }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);
    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(
        source
            .contains("Take $x$ in \\[0, 1\\], tag \\#3, and \\] \\#pagebreak() \\[ \\// ends it"),
        "{source}"
    );

    // Typst's SVG is glyph outlines with no text nodes, so the page count is what says the
    // characters were set rather than obeyed: an executed `#pagebreak()` would make two pages,
    // and an unescaped `]` would close the helper's block and fail to compile at all.
    let response = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": document, "output": "svg" }),
        )
        .await;
    assert_eq!(
        response.status().as_u16(),
        200,
        "{:?}",
        response.text().await
    );
    let body: Value = response.json().await.unwrap();
    assert_eq!(body["pages"].as_array().unwrap().len(), 1, "{body}");
}

#[tokio::test]
async fn a_field_whose_markup_does_not_compile_is_a_422_with_diagnostics() {
    let service = Service::start().await;
    let document = json!({
        "title": "Unbalanced",
        "questions": [{ "number": "1", "stem": "An unclosed $x^2" }],
    });

    let response = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": document }),
        )
        .await;
    assert_eq!(response.status().as_u16(), 422);

    let body: Value = response.json().await.unwrap();
    assert!(
        !body["diagnostics"].as_array().unwrap().is_empty(),
        "{body}"
    );
}

#[tokio::test]
async fn a_body_that_is_not_json_is_a_400() {
    let service = Service::start().await;

    let response = service
        .client
        .post(format!("{}/render", service.base))
        .header("content-type", "application/json")
        .body("{\"kind\":")
        .send()
        .await
        .unwrap();
    assert_eq!(response.status().as_u16(), 400);
}

/// A4 is 841.89pt tall; a fragment page is only as tall as the fragment.
const A4_HEIGHT: f64 = 841.89;

fn view_box_height(svg: &str) -> f64 {
    let value = svg
        .split_once("viewBox=\"")
        .unwrap()
        .1
        .split_once('"')
        .unwrap()
        .0;
    value.split_whitespace().nth(3).unwrap().parse().unwrap()
}

fn fragment() -> Value {
    json!({
        "number": "4",
        "stem": "The curve $C$ has equation $y = x^3 - 6x^2 + 9x + 1$.",
        "parts": [
            { "label": "a", "text": "Find $(d y) / (d x)$.", "marks": 2 },
            {
                "label": "b",
                "text": "Hence find the stationary points of $C$ and determine the nature of each.",
                "marks": 5,
            },
        ],
    })
}

#[tokio::test]
async fn a_question_fragment_is_one_svg_page_no_taller_than_it_needs() {
    let service = Service::start().await;

    let rendered = service
        .post(
            "/render",
            json!({ "kind": "question", "document": fragment(), "output": "source" }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);
    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(source.contains("#show: fragment"), "{source}");
    assert!(source.contains("#paper-question(\"4\", none)["), "{source}");
    assert!(source.contains("#part(\"b\", 5)["), "{source}");
    assert!(!source.contains("#show: paper"), "{source}");

    let response = service
        .post(
            "/render",
            json!({ "kind": "question", "document": fragment(), "output": "svg" }),
        )
        .await;
    assert_eq!(
        response.status().as_u16(),
        200,
        "{:?}",
        response.text().await
    );
    let body: Value = response.json().await.unwrap();
    let pages = body["pages"].as_array().unwrap();
    assert_eq!(pages.len(), 1, "{body}");

    let height = view_box_height(pages[0].as_str().unwrap());
    assert!(height > 0.0 && height < A4_HEIGHT / 3.0, "{height}pt");

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "question", "document": fragment(), "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

#[tokio::test]
async fn a_scheme_entry_is_rendered_under_the_question_it_belongs_to() {
    let service = Service::start().await;
    let scheme = json!({
        "number": "4",
        "parts": [
            {
                "label": "a",
                "answer": "$(d y) / (d x) = 3x^2 - 12x + 9$",
                "marks": 2,
                "notes": "M1 for any two terms correct.",
            },
        ],
    });

    let rendered = service
        .post(
            "/render",
            json!({
                "kind": "question",
                "document": fragment(),
                "mark_scheme": scheme,
                "output": "source",
            }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);
    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(source.contains("#paper-question(\"4\", none)["), "{source}");
    assert!(source.contains("#scheme-question(\"4\")["), "{source}");
    assert!(source.contains("#scheme-row(\"a\", 2)["), "{source}");
    assert!(source.contains("#scheme-note["), "{source}");

    let with_scheme = service
        .post(
            "/render",
            json!({
                "kind": "question",
                "document": fragment(),
                "mark_scheme": scheme,
                "output": "svg",
            }),
        )
        .await;
    assert_eq!(with_scheme.status().as_u16(), 200);
    let body: Value = with_scheme.json().await.unwrap();
    let pages = body["pages"].as_array().unwrap();
    assert_eq!(pages.len(), 1, "{body}");
    assert!(view_box_height(pages[0].as_str().unwrap()) < A4_HEIGHT / 2.0);

    let misplaced = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": { "title": "t" }, "mark_scheme": scheme }),
        )
        .await;
    assert_eq!(misplaced.status().as_u16(), 422);
    let body: Value = misplaced.json().await.unwrap();
    assert_eq!(body["errors"][0]["path"], "mark_scheme", "{body}");
}

#[tokio::test]
async fn a_markup_fragment_renders_one_page_and_obeys_nothing_in_it() {
    let service = Service::start().await;
    let document = json!({
        "text": "Show that $sum_(n=1)^(N) n = (N(N+1))/2$.\n\nState the *base case*, ] #pagebreak() [",
    });

    let rendered = service
        .post(
            "/render",
            json!({ "kind": "markup", "document": document, "output": "source" }),
        )
        .await;
    assert_eq!(rendered.status().as_u16(), 200);
    let source = rendered.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned();
    assert!(
        source.contains("base case*, \\] \\#pagebreak() \\["),
        "{source}"
    );

    let response = service
        .post(
            "/render",
            json!({ "kind": "markup", "document": document, "output": "svg" }),
        )
        .await;
    assert_eq!(
        response.status().as_u16(),
        200,
        "{:?}",
        response.text().await
    );
    let body: Value = response.json().await.unwrap();
    let pages = body["pages"].as_array().unwrap();
    assert_eq!(pages.len(), 1, "{body}");
    assert!(view_box_height(pages[0].as_str().unwrap()) < A4_HEIGHT / 4.0);
}

#[tokio::test]
async fn an_unknown_field_in_a_fragment_is_a_422_naming_the_path_to_it() {
    let service = Service::start().await;

    let question = service
        .post(
            "/render",
            json!({
                "kind": "question",
                "document": {
                    "number": "1",
                    "parts": [{ "label": "a", "text": "Find $x$.", "mark": 3 }],
                },
            }),
        )
        .await;
    assert_eq!(question.status().as_u16(), 422);
    let body: Value = question.json().await.unwrap();
    assert_eq!(body["errors"][0]["path"], "parts[0].mark", "{body}");
    assert!(
        body["errors"][0]["message"]
            .as_str()
            .unwrap()
            .contains("unknown field"),
        "{body}"
    );

    let scheme = service
        .post(
            "/render",
            json!({
                "kind": "question",
                "document": { "number": "1" },
                "mark_scheme": { "number": "1", "answr": "x = 2" },
            }),
        )
        .await;
    assert_eq!(scheme.status().as_u16(), 422);
    let body: Value = scheme.json().await.unwrap();
    assert_eq!(body["errors"][0]["path"], "mark_scheme.answr", "{body}");

    let markup = service
        .post(
            "/render",
            json!({ "kind": "markup", "document": { "text": "Hello.", "size": 12 } }),
        )
        .await;
    assert_eq!(markup.status().as_u16(), 422);
    let body: Value = markup.json().await.unwrap();
    assert_eq!(body["errors"][0]["path"], "size", "{body}");
}

/// A 1×1 truecolour PNG, written out here so the tests need no fixture file and no network.
const PIXEL_PNG: &str =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mNQcEgAAAFEAME1cEXuAAAAAElFTkSuQmCC";

async fn source_of(service: &Service, body: Value) -> String {
    let response = service.post("/render", body).await;
    assert_eq!(
        response.status().as_u16(),
        200,
        "{:?}",
        response.text().await
    );
    response.json::<Value>().await.unwrap()["source"]
        .as_str()
        .unwrap()
        .to_owned()
}

#[tokio::test]
async fn a_newline_in_a_field_is_a_line_break_and_a_blank_line_a_paragraph() {
    let service = Service::start().await;
    let document = json!({
        "title": "Lineation",
        "questions": [{
            "number": "1",
            "stem": "I met a traveller from an antique land,\nWho said—two vast legs of stone\n\nStand in the desert.",
        }],
    });

    let source = source_of(
        &service,
        json!({ "kind": "worksheet", "document": document, "output": "source" }),
    )
    .await;
    assert!(source.contains("antique land,\\\nWho said"), "{source}");
    assert!(
        source.contains("of stone\n\nStand in the desert."),
        "{source}"
    );

    // Three lines of verse where one prose line would fit: the breaks reached the page.
    let pages = service
        .post(
            "/render",
            json!({ "kind": "markup", "document": { "text": "one\ntwo\nthree" }, "output": "svg" }),
        )
        .await;
    assert_eq!(pages.status().as_u16(), 200);
    let body: Value = pages.json().await.unwrap();
    let broken = view_box_height(body["pages"][0].as_str().unwrap());

    let pages = service
        .post(
            "/render",
            json!({ "kind": "markup", "document": { "text": "one two three" }, "output": "svg" }),
        )
        .await;
    let body: Value = pages.json().await.unwrap();
    let flowed = view_box_height(body["pages"][0].as_str().unwrap());
    assert!(broken > flowed * 2.0, "{broken}pt against {flowed}pt");
}

#[tokio::test]
async fn a_section_carries_its_own_heading_choice_and_total() {
    let service = Service::start().await;
    let document = json!({
        "title": "English Literature",
        "total_marks": 75,
        "sections": [{
            "title": "Section A: Shakespeare",
            "instructions": "Answer *one* question in this section.",
            "choose": 1,
            "questions": [
                { "number": "01", "stem": "Explore the presentation of jealousy in *Othello*.", "marks": 25 },
                { "number": "02", "stem": "Explore the presentation of power in *Othello*.", "marks": 25 },
            ],
        }],
    });

    let source = source_of(
        &service,
        json!({ "kind": "paper", "document": document, "output": "source" }),
    )
    .await;
    // Two questions of 25 under a choice of one is 25 answerable marks, not 50, and the
    // paper's own total is untouched.
    assert!(source.contains("#section-heading("), "{source}");
    assert!(source.contains("], 1, 25)"), "{source}");
    assert!(source.contains("total-marks: 75"), "{source}");

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));

    let too_many = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": { "title": "t", "sections": [{ "choose": 3, "questions": [{ "number": "1" }] }] },
            }),
        )
        .await;
    assert_eq!(too_many.status().as_u16(), 422);
    let body: Value = too_many.json().await.unwrap();
    assert_eq!(body["errors"][0]["path"], "sections[0].choose", "{body}");
}

#[tokio::test]
async fn every_answer_type_calls_its_helper_and_compiles() {
    let service = Service::start().await;
    let document = json!({
        "title": "Answer spaces",
        "questions": [
            { "number": "1", "stem": "Ruled lines.", "answer": { "type": "lines", "lines": 3 } },
            { "number": "2", "stem": "A box.", "answer": { "type": "box", "height_mm": 30 } },
            { "number": "3", "stem": "Shade one lozenge.", "answer": { "type": "multiple_choice", "options": [
                { "text": "$2$" },
                { "label": "B", "text": "$20$" },
            ] } },
            { "number": "4", "stem": "An essay.", "answer": { "type": "essay", "height_mm": 60 } },
            { "number": "5", "stem": "A grid.", "answer": { "type": "grid", "rows": 6, "cols": 8 } },
            { "number": "6", "stem": "A table.", "answer": { "type": "table", "rows": 3, "cols": 4 } },
            { "number": "7", "stem": "Nothing at all.", "answer": { "type": "none" } },
        ],
    });

    let source = source_of(
        &service,
        json!({ "kind": "worksheet", "document": document, "output": "source" }),
    )
    .await;
    assert!(source.contains("#answerlines(3)"), "{source}");
    assert!(source.contains("#answer-box(30mm)"), "{source}");
    assert!(
        source.contains("(label: none, body: [\n$2$\n]),"),
        "{source}"
    );
    assert!(
        source.contains("(label: \"B\", body: [\n$20$\n]),"),
        "{source}"
    );
    assert!(source.contains("#answer-essay(60mm)"), "{source}");
    assert!(source.contains("#answer-grid(6, 8)"), "{source}");
    assert!(source.contains("#answer-table(3, 4)"), "{source}");

    let response = service
        .post(
            "/render",
            json!({ "kind": "worksheet", "document": document, "output": "svg" }),
        )
        .await;
    assert_eq!(
        response.status().as_u16(),
        200,
        "{:?}",
        response.text().await
    );
    let body: Value = response.json().await.unwrap();
    assert_eq!(body["pages"].as_array().unwrap().len(), 2, "{body}");

    let missing = service
        .post(
            "/render",
            json!({
                "kind": "worksheet",
                "document": { "title": "t", "questions": [{ "number": "1", "answer": { "type": "grid", "rows": 4 } }] },
            }),
        )
        .await;
    assert_eq!(missing.status().as_u16(), 422);
    let body: Value = missing.json().await.unwrap();
    assert_eq!(
        body["errors"][0]["path"], "questions[0].answer.cols",
        "{body}"
    );
}

#[tokio::test]
async fn an_answer_space_indents_with_the_part_it_belongs_to() {
    let service = Service::start().await;
    let document = json!({
        "title": "Indents",
        "questions": [{
            "number": "1",
            "parts": [{
                "label": "a",
                "text": "One.",
                "answer": { "type": "box" },
                "parts": [{ "label": "i", "text": "Two.", "answer": { "type": "lines", "lines": 2 } }],
            }],
        }],
    });

    let source = source_of(
        &service,
        json!({ "kind": "paper", "document": document, "output": "source" }),
    )
    .await;
    assert!(
        source.contains("#answer-box(40mm, indent: part-indent)"),
        "{source}"
    );
    assert!(
        source.contains("#answerlines(2, indent: part-indent * 2)"),
        "{source}"
    );
}

#[tokio::test]
async fn a_passage_keeps_its_lines_and_a_listing_its_indentation() {
    let service = Service::start().await;
    let document = json!({
        "title": "Blocks",
        "passages": [{
            "id": "sonnet",
            "title": "Ozymandias",
            "text": "I met a traveller from an antique land,\nWho said—\"Two vast and trunkless legs of stone\"",
        }],
        "questions": [{
            "number": "1",
            "stem": "Read the passage and the program.",
            "blocks": [
                { "type": "passage_ref", "id": "sonnet" },
                { "type": "passage", "title": "An extract", "text": "First line.\nSecond line." },
                { "type": "code", "language": "python", "text": "def total(values):\n    return sum(values)" },
                { "type": "table", "caption": "Table 1", "header": ["Gate", "Time / $s$"],
                  "rows": [["A", "0.00"], ["B", "0.41"]] },
            ],
        }],
    });

    let source = source_of(
        &service,
        json!({ "kind": "paper", "document": document, "output": "source" }),
    )
    .await;
    // The passage is a Typst string, not markup: its newlines survive as `\n` in the literal.
    assert!(
        source.contains(
            "#passage-block([\nOzymandias\n], \"I met a traveller from an antique land,\\nWho said"
        ),
        "{source}"
    );
    assert!(
        source.contains("#passage-block([\nAn extract\n], \"First line.\\nSecond line.\")"),
        "{source}"
    );
    assert!(
        source.contains("#code-block(\"python\", \"def total(values):\\n    return sum(values)\")"),
        "{source}"
    );
    assert!(
        source.contains("#data-table([\nTable 1\n], ([\nGate\n], [\nTime / $s$\n], ), ("),
        "{source}"
    );
    assert!(
        source.contains("#passage-ref([\nOzymandias\n])"),
        "{source}"
    );

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));

    let dangling = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": { "title": "t", "questions": [{ "number": "1", "blocks": [{ "type": "passage_ref", "id": "nowhere" }] }] },
            }),
        )
        .await;
    assert_eq!(dangling.status().as_u16(), 422);
    let body: Value = dangling.json().await.unwrap();
    assert_eq!(
        body["errors"][0]["path"], "questions[0].blocks[0].id",
        "{body}"
    );

    let ragged = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": { "title": "t", "questions": [{ "number": "1", "blocks": [
                    { "type": "table", "header": ["a", "b"], "rows": [["1"]] },
                ] }] },
            }),
        )
        .await;
    assert_eq!(ragged.status().as_u16(), 422);
    let body: Value = ragged.json().await.unwrap();
    assert_eq!(
        body["errors"][0]["path"], "questions[0].blocks[0].rows[0]",
        "{body}"
    );
}

fn figure() -> Value {
    json!({
        "title": "Figures",
        "questions": [{
            "number": "1",
            "stem": "The circuit is shown below.",
            "blocks": [{ "type": "figure", "asset": "figure-1.png", "caption": "Figure 1", "width_mm": 40 }],
        }],
    })
}

#[tokio::test]
async fn a_figure_renders_from_an_asset_and_a_missing_one_is_refused() {
    let service = Service::start().await;

    let source = source_of(
        &service,
        json!({
            "kind": "paper",
            "document": figure(),
            "assets": { "figure-1.png": PIXEL_PNG },
            "output": "source",
        }),
    )
    .await;
    assert!(
        source.contains("#figure-block(\"figure-1.png\", [\nFigure 1\n], 40mm)"),
        "{source}"
    );

    let compiled = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": figure(),
                "assets": { "figure-1.png": PIXEL_PNG },
                "output": "pdf",
            }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));

    // A fragment takes assets too, so the app can show one question with its figure.
    let fragment = service
        .post(
            "/render",
            json!({
                "kind": "question",
                "document": {
                    "number": "1",
                    "blocks": [{ "type": "figure", "asset": "figure-1.png" }],
                },
                "assets": { "figure-1.png": PIXEL_PNG },
                "output": "svg",
            }),
        )
        .await;
    assert_eq!(
        fragment.status().as_u16(),
        200,
        "{:?}",
        fragment.text().await
    );
    let body: Value = fragment.json().await.unwrap();
    assert_eq!(body["pages"].as_array().unwrap().len(), 1, "{body}");

    let missing = service
        .post("/render", json!({ "kind": "paper", "document": figure() }))
        .await;
    assert_eq!(missing.status().as_u16(), 422);
    let body: Value = missing.json().await.unwrap();
    assert_eq!(
        body["errors"][0]["path"], "questions[0].blocks[0].asset",
        "{body}"
    );
    assert!(
        body["errors"][0]["message"]
            .as_str()
            .unwrap()
            .contains("figure-1.png"),
        "{body}"
    );

    // A name that is a path, or a format the compiler cannot read, never reaches the compiler.
    let path = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": { "title": "t" },
                "assets": { "../secret.png": PIXEL_PNG },
            }),
        )
        .await;
    assert_eq!(path.status().as_u16(), 422);
    let body: Value = path.json().await.unwrap();
    assert_eq!(body["errors"][0]["path"], "assets.../secret.png", "{body}");
}

#[tokio::test]
async fn an_oversize_asset_is_a_413() {
    let service = Service::start().await;
    // Valid base64 that decodes to more than one asset may be.
    let oversize = "A".repeat(2_800_000);

    let response = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": { "title": "t" },
                "assets": { "big.png": oversize },
            }),
        )
        .await;
    assert_eq!(response.status().as_u16(), 413);
    let body: Value = response.json().await.unwrap();
    assert!(
        body["message"].as_str().unwrap().contains("big.png"),
        "{body}"
    );
}

#[tokio::test]
async fn a_mark_scheme_entry_may_carry_a_marking_table() {
    let service = Service::start().await;
    let document = json!({
        "title": "Marking",
        "questions": [{
            "number": "1",
            "parts": [{
                "label": "a",
                "answer": "$r = 1/4$",
                "marks": 3,
                "blocks": [{ "type": "table", "header": ["Step", "Mark"], "rows": [["Substitutes", "M1"], ["Answer", "A1"]] }],
            }],
        }],
    });

    let source = source_of(
        &service,
        json!({ "kind": "mark_scheme", "document": document, "output": "source" }),
    )
    .await;
    assert!(source.contains("#scheme-row(\"a\", 3)["), "{source}");
    assert!(
        source.contains("#data-table(none, ([\nStep\n], [\nMark\n], ), ("),
        "{source}"
    );

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "mark_scheme", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

#[tokio::test]
async fn a_document_written_before_answer_types_renders_as_it_did() {
    let service = Service::start().await;

    let source = source_of(
        &service,
        json!({ "kind": "paper", "document": paper(), "output": "source" }),
    )
    .await;
    // The last occurrence: the templates mention the `#show:` line in their own comments.
    let body = source.rsplit("#show: paper.with(").next().unwrap();
    for added in [
        "#answer-",
        "#section-heading(",
        "#passage-block(",
        "#passage-ref(",
        "#code-block(",
        "#data-table(",
        "#figure-block(",
    ] {
        assert!(!body.contains(added), "{added} in\n{body}");
    }
    assert!(
        body.contains("#answerlines(3, indent: part-indent)"),
        "{body}"
    );
    assert!(body.contains("#answerlines(4)"), "{body}");

    // `answer_lines` is the older spelling of the same thing, and saying both is refused.
    let both = service
        .post(
            "/render",
            json!({
                "kind": "paper",
                "document": { "title": "t", "questions": [{
                    "number": "1", "answer_lines": 3, "answer": { "type": "lines", "lines": 3 },
                }] },
            }),
        )
        .await;
    assert_eq!(both.status().as_u16(), 422);
    let body: Value = both.json().await.unwrap();
    assert_eq!(
        body["errors"][0]["path"], "questions[0].answer_lines",
        "{body}"
    );
}

/// Prose a real paper contains that Typst would otherwise read as syntax.
const AWKWARD: [&str; 11] = [
    "The region where a < b and the region where x > y.",
    "Write to email@example.com before <the deadline>.",
    "A lone ` backtick and a 5 <3 comparison.",
    "*unbalanced prose and a _lone underscore.",
    "Costs rose 20% -- a * b -- and fell again.",
    "Given $a < b$ and $x >= y$, show that a < x.",
    "Use *bold* and _emph_ as before, with snake_case_name intact.",
    "Divide a */ b and then / halve it",
    "/ no colon on this line",
    "The *quick _brown* fox_ crossed over.",
    "- one *asterisk\n- two *asterisks",
];

#[tokio::test]
async fn prose_that_looks_like_typst_syntax_still_renders() {
    let service = Service::start().await;

    for text in AWKWARD {
        let response = service
            .post(
                "/render",
                json!({ "kind": "markup", "document": { "text": text }, "output": "svg" }),
            )
            .await;
        assert_eq!(
            response.status().as_u16(),
            200,
            "{text}\n{:?}",
            response.text().await
        );
        let body: Value = response.json().await.unwrap();
        assert_eq!(body["pages"].as_array().unwrap().len(), 1, "{text} {body}");
    }

    // The same prose in every markup field of a paper, and in a table's cells.
    let document = json!({
        "title": "Awkward prose",
        "instructions": AWKWARD[0],
        "questions": [{
            "number": "1",
            "stem": AWKWARD[1],
            "blocks": [{ "type": "table", "caption": AWKWARD[2], "header": ["a < b", "x > y"],
                         "rows": [[AWKWARD[3], AWKWARD[4]], [AWKWARD[7], AWKWARD[9]]] }],
            "parts": [{
                "label": "a",
                "text": AWKWARD[5],
                "answer": { "type": "multiple_choice", "options": [
                    { "text": AWKWARD[3] }, { "text": AWKWARD[8] }, { "text": AWKWARD[10] },
                ] },
            }],
        }],
    });
    let compiled = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

#[tokio::test]
async fn a_passage_and_a_listing_take_the_same_prose_verbatim() {
    let service = Service::start().await;
    // A passage is a Typst string, so none of this is syntax — but a quote, a backslash or a
    // newline would still close the literal if they were not escaped.
    let awkward = "if (a < b) { print(\"x > y\"); }\n\tmail@example.com `tick` *star* \\ end";
    let document = json!({
        "title": "Verbatim",
        "questions": [{
            "number": "1",
            "blocks": [
                { "type": "passage", "title": "a < b", "text": awkward },
                { "type": "code", "language": "c", "text": awkward },
            ],
        }],
    });

    let source = source_of(
        &service,
        json!({ "kind": "paper", "document": document, "output": "source" }),
    )
    .await;
    assert!(
        source.contains("\\\"x \\u{3e} y\\\"") || source.contains("\\\"x > y\\\""),
        "{source}"
    );
    assert!(
        source.contains("\\n\\tmail@example.com `tick` *star* \\\\ end"),
        "{source}"
    );

    let compiled = service
        .post(
            "/render",
            json!({ "kind": "paper", "document": document, "output": "pdf" }),
        )
        .await;
    assert_eq!(
        compiled.status().as_u16(),
        200,
        "{:?}",
        compiled.text().await
    );
    assert!(compiled.bytes().await.unwrap().starts_with(b"%PDF"));
}

/// Typst's SVG is one `<use>` per glyph, so a soft hyphen is one glyph that no character in
/// the title accounts for.
fn glyphs(svg: &str) -> usize {
    svg.matches("<use ").count()
}

fn visible(text: &str) -> usize {
    text.chars()
        .filter(|character| !character.is_whitespace())
        .count()
}

async fn one_page(service: &Service, kind: &str, document: Value) -> String {
    let response = service
        .post(
            "/render",
            json!({ "kind": kind, "document": document, "output": "svg" }),
        )
        .await;
    assert_eq!(
        response.status().as_u16(),
        200,
        "{:?}",
        response.text().await
    );
    let body: Value = response.json().await.unwrap();
    let pages = body["pages"].as_array().unwrap();
    assert_eq!(pages.len(), 1, "{body}");
    pages[0].as_str().unwrap().to_owned()
}

#[tokio::test]
async fn a_long_title_wraps_without_a_soft_hyphen() {
    let service = Service::start().await;
    // The real paper that hyphenated as "Non-Calcu-lator".
    const LONG: &str = "GCSE Mathematics Higher Tier Paper 1 Non-Calculator";
    const SHORT: &str = "GCSE";

    let paper = |title: &str| {
        json!({
            "title": title,
            "questions": [{ "number": "1", "stem": "Work it out.", "marks": 2 }],
        })
    };

    let source = source_of(
        &service,
        json!({ "kind": "paper", "document": paper(LONG), "output": "source" }),
    )
    .await;
    assert!(source.contains("hyphenate: false"), "{source}");

    // Two pages that differ only in the title: the longer one costs exactly one glyph per
    // visible character it added. A hyphenated break would cost one more.
    let long = glyphs(&one_page(&service, "paper", paper(LONG)).await);
    let short = glyphs(&one_page(&service, "paper", paper(SHORT)).await);
    assert_eq!(
        long - short,
        visible(LONG) - visible(SHORT),
        "the title was broken with a hyphen: {long} glyphs against {short}"
    );

    // The same for the headings of the other kinds, and for a section's title.
    let worksheet = |title: &str| json!({ "title": title, "questions": [] });
    let long = glyphs(&one_page(&service, "worksheet", worksheet(LONG)).await);
    let short = glyphs(&one_page(&service, "worksheet", worksheet(SHORT)).await);
    assert_eq!(long - short, visible(LONG) - visible(SHORT));

    let scheme = |title: &str| json!({ "title": title, "questions": [] });
    let long = glyphs(&one_page(&service, "mark_scheme", scheme(LONG)).await);
    let short = glyphs(&one_page(&service, "mark_scheme", scheme(SHORT)).await);
    assert_eq!(long - short, visible(LONG) - visible(SHORT));

    let section = |title: &str| {
        json!({
            "title": "t",
            "sections": [{ "title": title, "questions": [{ "number": "1", "marks": 3 }] }],
        })
    };
    let long = glyphs(&one_page(&service, "paper", section(LONG)).await);
    let short = glyphs(&one_page(&service, "paper", section(SHORT)).await);
    assert_eq!(long - short, visible(LONG) - visible(SHORT));
}
