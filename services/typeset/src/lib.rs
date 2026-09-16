//! Typst, embedded. The compiler runs in-process against a world that has no filesystem, no
//! package cache and no network; the only fonts are the ones compiled into the binary.

mod api;
mod compile;
mod document;
mod render;
mod template;

pub use api::{COMPILE_TIMEOUT, MAX_SOURCE_BYTES, RenderOutput, RenderRequest, router};
pub use compile::{Compiled, Diagnostic, Output, compile};
pub use document::{
    Document, DocumentKind, MAX_ANSWER_LINES, MarkScheme, MarkSchemePart, MarkSchemeQuestion,
    Markup, Paper, Part, Question, ValidationError, Worksheet,
};
pub use render::render;
pub use template::wrap_homework;
