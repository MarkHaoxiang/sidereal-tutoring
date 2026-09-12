//! Typst, embedded. The compiler runs in-process against a world that has no filesystem, no
//! package cache and no network; the only fonts are the ones compiled into the binary.

mod api;
mod compile;
mod template;

pub use api::{COMPILE_TIMEOUT, MAX_SOURCE_BYTES, router};
pub use compile::{Compiled, Diagnostic, Output, compile};
pub use template::wrap_homework;
