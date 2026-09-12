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
