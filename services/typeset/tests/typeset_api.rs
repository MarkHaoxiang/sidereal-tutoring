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
