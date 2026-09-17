//! Typst, embedded. The compiler runs in-process against a world that has no filesystem, no
//! package cache and no network; the only fonts are the ones compiled into the binary.

mod api;
mod assets;
mod compile;
mod document;
mod render;
mod template;

pub use api::{COMPILE_TIMEOUT, MAX_SOURCE_BYTES, RenderOutput, RenderRequest, router};
pub use assets::{AssetError, Assets, MAX_ASSET_BYTES, MAX_ASSET_NAME, MAX_ASSETS_BYTES};
pub use compile::{Compiled, Diagnostic, Output, compile};
pub use document::{
    Answer, AnswerKind, AnswerOption, Block, Document, DocumentKind, MAX_ANSWER_HEIGHT_MM,
    MAX_ANSWER_LINES, MAX_ANSWER_OPTIONS, MAX_FIGURE_WIDTH_MM, MAX_GRID_COLS, MAX_GRID_ROWS,
    MAX_TABLE_COLS, MAX_TABLE_ROWS, MarkScheme, MarkSchemePart, MarkSchemeQuestion, Markup, Paper,
    Part, Passage, Question, Section, ValidationError, Worksheet,
};
pub use render::render;
pub use template::wrap_homework;
