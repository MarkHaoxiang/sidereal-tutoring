use std::fmt::Write as _;
use std::time::Duration;

use axum::body::Bytes;
use axum::extract::DefaultBodyLimit;
use axum::http::{StatusCode, header};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use serde_path_to_error::{Path, Segment};

use crate::compile::{Compiled, Diagnostic, Output, compile};
use crate::document::{Document, DocumentKind, MarkScheme, Paper, ValidationError, Worksheet};
use crate::render::render;
use crate::template::wrap_homework;

/// The largest source the service will compile or wrap.
pub const MAX_SOURCE_BYTES: usize = 256 * 1024;

/// How long one compilation may run before the caller is told it timed out.
pub const COMPILE_TIMEOUT: Duration = Duration::from_secs(10);

/// JSON escaping can inflate a source several times over, so the transport limit is looser
/// than `MAX_SOURCE_BYTES`; the decoded source is what the handlers actually measure.
const MAX_BODY_BYTES: usize = 4 * MAX_SOURCE_BYTES + 64 * 1024;

pub fn router() -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .route("/compile", post(compile_source))
        .route("/template", post(apply_template))
        .route("/render", post(render_document))
        .layer(DefaultBodyLimit::max(MAX_BODY_BYTES))
}

/// Liveness only: the compiler is in-process, so this says the service is up and nothing more.
async fn healthz() -> (StatusCode, &'static str) {
    (StatusCode::OK, "ok")
}

#[derive(Debug, Deserialize)]
pub struct CompileRequest {
    pub source: String,
    #[serde(default = "pdf")]
    pub output: Output,
}

fn pdf() -> Output {
    Output::Pdf
}

#[derive(Debug, Serialize)]
struct SvgPages {
    pages: Vec<String>,
}

async fn compile_source(Json(request): Json<CompileRequest>) -> Result<Response, ApiError> {
    compiled_response(request.source, request.output).await
}

async fn compiled_response(source: String, output: Output) -> Result<Response, ApiError> {
    let bytes = source.len();
    if bytes > MAX_SOURCE_BYTES {
        return Err(ApiError::TooLarge(bytes));
    }

    // The compiler is synchronous and CPU-bound; the timeout cannot cancel it, but Typst caps
    // loop iterations, so a blocking task always finishes and the pool cannot fill up.
    let task = tokio::task::spawn_blocking(move || compile(&source, output));
    let compiled = match tokio::time::timeout(COMPILE_TIMEOUT, task).await {
        Ok(Ok(compiled)) => compiled,
        Ok(Err(error)) => return Err(ApiError::Failed(error.to_string())),
        Err(_) => {
            tracing::warn!(bytes, ?output, "compilation timed out");
            return Err(ApiError::Timeout);
        }
    };

    match compiled {
        Ok(Compiled::Pdf(pdf)) => {
            tracing::info!(bytes, pdf_bytes = pdf.len(), "compiled a pdf");
            Ok(([(header::CONTENT_TYPE, "application/pdf")], pdf).into_response())
        }
        Ok(Compiled::Svg(pages)) => {
            tracing::info!(bytes, pages = pages.len(), "compiled svg pages");
            Ok(Json(SvgPages { pages }).into_response())
        }
        Err(diagnostics) => {
            tracing::info!(bytes, count = diagnostics.len(), "source did not compile");
            Err(ApiError::Diagnostics(diagnostics))
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TemplateKind {
    Homework,
}

#[derive(Debug, Deserialize)]
pub struct TemplateRequest {
    pub kind: TemplateKind,
    pub title: String,
    #[serde(default)]
    pub student: Option<String>,
    #[serde(default)]
    pub due: Option<String>,
    pub body: String,
}

#[derive(Debug, Serialize)]
struct TemplateResponse {
    source: String,
}

async fn apply_template(Json(request): Json<TemplateRequest>) -> Result<Response, ApiError> {
    let bytes = request.body.len();
    if bytes > MAX_SOURCE_BYTES {
        return Err(ApiError::TooLarge(bytes));
    }

    let TemplateKind::Homework = request.kind;
    let source = wrap_homework(
        &request.title,
        request.student.as_deref(),
        request.due.as_deref(),
        &request.body,
    );
    tracing::info!(
        bytes,
        source_bytes = source.len(),
        "wrapped a homework body"
    );
    Ok(Json(TemplateResponse { source }).into_response())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RenderOutput {
    Pdf,
    Svg,
    Source,
}

fn render_pdf() -> RenderOutput {
    RenderOutput::Pdf
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RenderRequest {
    pub kind: DocumentKind,
    pub document: Value,
    #[serde(default = "render_pdf")]
    pub output: RenderOutput,
}

/// The body is read here rather than by `Json` so that a field serde cannot read is answered
/// with the path to it instead of a bare message.
async fn render_document(body: Bytes) -> Result<Response, ApiError> {
    let request: RenderRequest = from_slice(&body)?;
    let document = match request.kind {
        DocumentKind::Paper => Document::Paper(from_value::<Paper>(request.document)?),
        DocumentKind::MarkScheme => {
            Document::MarkScheme(from_value::<MarkScheme>(request.document)?)
        }
        DocumentKind::Worksheet => Document::Worksheet(from_value::<Worksheet>(request.document)?),
    };

    let errors = document.validate();
    if !errors.is_empty() {
        tracing::info!(count = errors.len(), "document did not validate");
        return Err(ApiError::Invalid(errors));
    }

    let source = render(&document);
    tracing::info!(
        ?request.kind,
        ?request.output,
        source_bytes = source.len(),
        "rendered a document"
    );
    match request.output {
        RenderOutput::Source => {
            if source.len() > MAX_SOURCE_BYTES {
                return Err(ApiError::TooLarge(source.len()));
            }
            Ok(Json(TemplateResponse { source }).into_response())
        }
        RenderOutput::Pdf => compiled_response(source, Output::Pdf).await,
        RenderOutput::Svg => compiled_response(source, Output::Svg).await,
    }
}

fn from_slice<T: DeserializeOwned>(bytes: &[u8]) -> Result<T, ApiError> {
    let mut deserializer = serde_json::Deserializer::from_slice(bytes);
    serde_path_to_error::deserialize(&mut deserializer).map_err(|error| {
        match error.inner().classify() {
            serde_json::error::Category::Syntax | serde_json::error::Category::Eof => {
                ApiError::BadJson(error.inner().to_string())
            }
            _ => ApiError::Invalid(vec![invalid(error)]),
        }
    })
}

/// The document is deserialized on its own so the reported paths are rooted at the document,
/// as the field names in the structure are.
fn from_value<T: DeserializeOwned>(document: Value) -> Result<T, ApiError> {
    serde_path_to_error::deserialize(document)
        .map_err(|error| ApiError::Invalid(vec![invalid(error)]))
}

fn invalid(error: serde_path_to_error::Error<serde_json::Error>) -> ValidationError {
    ValidationError {
        path: path(error.path()),
        message: error.inner().to_string(),
    }
}

/// serde's own path, spelled the way the structure is indexed: `questions[2].parts[0].marks`.
fn path(path: &Path) -> String {
    let mut out = String::new();
    for segment in path.iter() {
        match segment {
            Segment::Seq { index } => {
                let _ = write!(out, "[{index}]");
            }
            Segment::Map { key } | Segment::Enum { variant: key } => {
                if !out.is_empty() {
                    out.push('.');
                }
                out.push_str(key);
            }
            _ => {}
        }
    }
    out
}

/// Everything that is not a successful response. A source the compiler rejects is a 422
/// carrying its diagnostics — never a 500.
#[derive(Debug)]
enum ApiError {
    Diagnostics(Vec<Diagnostic>),
    Invalid(Vec<ValidationError>),
    BadJson(String),
    TooLarge(usize),
    Timeout,
    Failed(String),
}

#[derive(Debug, Serialize)]
struct Invalid {
    errors: Vec<ValidationError>,
}

#[derive(Debug, Serialize)]
struct Diagnostics {
    diagnostics: Vec<Diagnostic>,
}

#[derive(Debug, Serialize)]
struct Message {
    message: String,
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        match self {
            Self::Diagnostics(diagnostics) => (
                StatusCode::UNPROCESSABLE_ENTITY,
                Json(Diagnostics { diagnostics }),
            )
                .into_response(),
            Self::Invalid(errors) => {
                (StatusCode::UNPROCESSABLE_ENTITY, Json(Invalid { errors })).into_response()
            }
            Self::BadJson(message) => {
                (StatusCode::BAD_REQUEST, Json(Message { message })).into_response()
            }
            Self::TooLarge(bytes) => (
                StatusCode::PAYLOAD_TOO_LARGE,
                Json(Message {
                    message: format!(
                        "the source is {bytes} bytes; the limit is {MAX_SOURCE_BYTES}"
                    ),
                }),
            )
                .into_response(),
            Self::Timeout => (
                StatusCode::REQUEST_TIMEOUT,
                Json(Message {
                    message: format!("compilation exceeded {} seconds", COMPILE_TIMEOUT.as_secs()),
                }),
            )
                .into_response(),
            Self::Failed(error) => {
                tracing::error!(%error, "the compiler task did not finish");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(Message {
                        message: "the compiler task did not finish".to_owned(),
                    }),
                )
                    .into_response()
            }
        }
    }
}
