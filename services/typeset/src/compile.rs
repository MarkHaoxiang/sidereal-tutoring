use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::LazyLock;

use serde::Serialize;
use typst::World;
use typst::WorldExt;
use typst::diag::{
    EcoString, EcoVec, FileError, FileResult, PackageError, Severity, SourceDiagnostic,
};
use typst::foundations::Bytes;
use typst::syntax::ast::AstNode;
use typst::syntax::{FileId, Source, Span, SyntaxNode, VirtualRoot, ast};
use typst::text::Font;
use typst_as_lib::TypstEngine;
use typst_as_lib::file_resolver::FileResolver;
use typst_layout::PagedDocument;
use typst_pdf::PdfOptions;
use typst_svg::SvgOptions;

use crate::assets::Assets;

/// The fonts the compiler may use, parsed once. Only these exist: nothing reads the host's
/// font directories, so a document renders identically wherever the binary runs.
static FONTS: LazyLock<Vec<Font>> = LazyLock::new(|| {
    typst_assets::fonts()
        .flat_map(|data| Font::iter(Bytes::new(data)))
        .collect()
});

/// What a caller asked the compiler to produce.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Output {
    Pdf,
    Svg,
}

/// A finished compilation.
#[derive(Debug)]
pub enum Compiled {
    Pdf(Vec<u8>),
    Svg(Vec<String>),
}

/// One compiler message, positioned in the submitted source. `line` and `column` are 1-based
/// and absent only for a diagnostic that points at no source at all.
#[derive(Debug, Clone, Serialize)]
pub struct Diagnostic {
    pub message: String,
    pub line: Option<usize>,
    pub column: Option<usize>,
    pub severity: &'static str,
}

impl Diagnostic {
    fn detached(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            line: None,
            column: None,
            severity: "error",
        }
    }

    fn at(source: &Source, span: Span, message: impl Into<String>) -> Self {
        let position = source
            .find(span)
            .and_then(|node| position(source, node.range().start));
        Self {
            message: message.into(),
            line: position.map(|(line, _)| line),
            column: position.map(|(_, column)| column),
            severity: "error",
        }
    }
}

/// Compiles `text`, blocking the calling thread for as long as the compiler runs. `assets`
/// are the only files that exist: the figures that came with the request, keyed by name.
///
/// The error case is the compiler's own diagnostics; a caller turns them into a 422 rather
/// than a failure of the service.
pub fn compile(text: &str, output: Output, assets: &Assets) -> Result<Compiled, Vec<Diagnostic>> {
    let source = Source::detached(text.to_owned());

    let blocked = blocked_imports(&source);
    if !blocked.is_empty() {
        return Err(blocked);
    }

    // `main_file` registers the source's own resolver first, so `Files` only ever answers for
    // an id the document asked for itself, and its error is the one the compiler reports.
    let engine = TypstEngine::builder()
        .main_file(source.clone())
        .fonts(FONTS.iter().cloned())
        .add_file_resolver(Files::new(assets))
        .build();

    let outcome = engine.with_world(|world| {
        let report = |errors: EcoVec<SourceDiagnostic>| diagnostics(world, &source, &errors);
        let document = typst::compile::<PagedDocument>(world)
            .output
            .map_err(report)?;
        match output {
            Output::Pdf => typst_pdf::pdf(&document, &PdfOptions::default())
                .map(Compiled::Pdf)
                .map_err(report),
            Output::Svg => Ok(Compiled::Svg(
                document
                    .pages()
                    .iter()
                    .map(|page| typst_svg::svg(page, &SvgOptions::default()))
                    .collect(),
            )),
        }
    });

    match outcome {
        Ok(result) => result,
        Err(error) => Err(vec![Diagnostic::detached(error.to_string())]),
    }
}

/// Rejects `@preview` and other package imports before the compiler can ask for them, so the
/// caller gets one clear message instead of a load failure — and so a crafted document cannot
/// mint file ids for packages that will never resolve.
fn blocked_imports(source: &Source) -> Vec<Diagnostic> {
    fn walk(node: &SyntaxNode, found: &mut Vec<(EcoString, Span)>) {
        let target = node
            .cast::<ast::ModuleImport>()
            .map(ast::ModuleImport::source)
            .or_else(|| {
                node.cast::<ast::ModuleInclude>()
                    .map(ast::ModuleInclude::source)
            });
        if let Some(ast::Expr::Str(literal)) = target {
            let value = literal.get();
            if value.starts_with('@') {
                found.push((value, literal.to_untyped().span()));
            }
        }
        for child in node.children() {
            walk(child, found);
        }
    }

    let mut found = Vec::new();
    walk(source.root(), &mut found);
    found
        .into_iter()
        .map(|(spec, span)| {
            Diagnostic::at(
                source,
                span,
                format!(
                    "package imports are not available: this service compiles offline, so \
                     `{spec}` cannot be downloaded. Use the Typst standard library or the \
                     helpers from the house template instead."
                ),
            )
        })
        .collect()
}

/// The whole filesystem the document gets: the request's own figures, held in memory and
/// looked up by name with the path thrown away. Registered after the main source's own
/// resolver, so `read`, `include`, a package import and an `image` of anything else all end
/// here with an explicit reason. With no assets it denies everything, as it always did.
#[derive(Debug)]
struct Files {
    binaries: HashMap<String, Bytes>,
}

impl Files {
    fn new(assets: &Assets) -> Self {
        Self {
            binaries: assets
                .iter()
                .map(|(name, bytes)| (name.to_owned(), Bytes::new(bytes.to_vec())))
                .collect(),
        }
    }

    fn denied(&self, id: FileId) -> FileError {
        match id.root() {
            VirtualRoot::Package(spec) => {
                FileError::Package(PackageError::Other(Some(EcoString::from(format!(
                    "{spec} is not available: this service compiles offline"
                )))))
            }
            VirtualRoot::Project if self.binaries.is_empty() => {
                FileError::Other(Some(EcoString::from(format!(
                    "this service has no filesystem, so `{}` cannot be read",
                    id.vpath().get_without_slash()
                ))))
            }
            VirtualRoot::Project => FileError::Other(Some(EcoString::from(format!(
                "this service has no filesystem: `{}` is not one of the assets sent with this \
                 request",
                id.vpath().get_without_slash()
            )))),
        }
    }
}

impl FileResolver for Files {
    fn resolve_binary(&self, id: FileId) -> FileResult<Cow<'_, Bytes>> {
        if let VirtualRoot::Project = id.root() {
            let path = id.vpath().get_without_slash();
            let name = path.rsplit('/').next().unwrap_or(path);
            if let Some(bytes) = self.binaries.get(name) {
                return Ok(Cow::Borrowed(bytes));
            }
        }
        Err(self.denied(id))
    }

    fn resolve_source(&self, id: FileId) -> FileResult<Cow<'_, Source>> {
        Err(self.denied(id))
    }
}

fn diagnostics(world: &dyn World, source: &Source, errors: &[SourceDiagnostic]) -> Vec<Diagnostic> {
    errors
        .iter()
        .map(|error| {
            let position = world
                .range(error.span)
                .and_then(|range| position(source, range.start));
            Diagnostic {
                message: error.message.to_string(),
                line: position.map(|(line, _)| line),
                column: position.map(|(_, column)| column),
                severity: match error.severity {
                    Severity::Error => "error",
                    Severity::Warning => "warning",
                },
            }
        })
        .collect()
}

/// The 1-based line and column of a byte offset in the submitted source.
fn position(source: &Source, offset: usize) -> Option<(usize, usize)> {
    let (line, column) = source.lines().byte_to_line_column(offset)?;
    Some((line + 1, column + 1))
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used, clippy::panic)]

    use super::{Output, compile};
    use crate::assets::Assets;

    #[test]
    fn the_embedded_fonts_include_new_computer_modern() {
        let families: Vec<_> = super::FONTS
            .iter()
            .map(|font| font.info().family.clone())
            .collect();
        assert!(
            families
                .iter()
                .any(|family| family == "New Computer Modern"),
            "{families:?}"
        );
        assert!(
            families
                .iter()
                .any(|family| family == "New Computer Modern Math"),
            "{families:?}"
        );
    }

    #[test]
    fn a_file_read_is_refused_with_a_reason() {
        let errors =
            compile("#read(\"/etc/passwd\")", Output::Pdf, &Assets::default()).unwrap_err();
        let message = &errors[0].message;
        assert!(message.contains("no filesystem"), "{message}");
    }
}
