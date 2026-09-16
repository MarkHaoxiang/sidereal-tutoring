//! Structure to Typst markup. Layout lives in `template/`; this module only decides which
//! helper each node calls and how a tutor's text is made safe to place inside `[ ]`.

use std::fmt::Display;
use std::fmt::Write as _;

use crate::document::{
    Document, MarkScheme, MarkSchemeQuestion, Markup, Paper, Part, Question, Worksheet,
};
use crate::template::{
    fragment_preamble, literal, mark_scheme_preamble, paper_preamble, quoted, worksheet_preamble,
};

/// The complete source for `document`: the template it needs, its `#show:` line, and its
/// questions as calls to the template's helpers.
pub fn render(document: &Document) -> String {
    match document {
        Document::Paper(paper) => paper_source(paper),
        Document::MarkScheme(scheme) => mark_scheme_source(scheme),
        Document::Worksheet(worksheet) => worksheet_source(worksheet),
        Document::Question { question, scheme } => question_source(question, scheme.as_ref()),
        Document::Markup(fragment) => markup_source(fragment),
    }
}

/// A tutor's field carries Typst markup — `$x^2$`, `*bold*`, `_emph_`, lists — and is placed
/// inside a helper's `[ ]` block. Four characters could leave that block or start code, so
/// each is escaped: the backslash first (or it would re-arm the others), then `#`, `[` and
/// `]`. `/` is escaped only where it would open a comment. The emitted block is therefore
/// always balanced and never executes: a field cannot call a Typst function, and layout stays
/// the template's job. Markup that is merely wrong — unclosed `$`, say — still reaches the
/// compiler and comes back as a diagnostic.
fn markup(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut characters = text.chars().peekable();
    while let Some(character) = characters.next() {
        match character {
            '\\' | '#' | '[' | ']' => {
                out.push('\\');
                out.push(character);
            }
            '/' if matches!(characters.peek(), Some('/' | '*')) => out.push_str("\\/"),
            _ => out.push(character),
        }
    }
    out
}

/// A helper's content argument, always a block so the call keeps its trailing argument, and
/// on its own lines so the source stays readable and a field that starts a list or a heading
/// still means what it said.
fn content(text: &str) -> String {
    let text = text.trim();
    if text.is_empty() {
        return "[]".to_owned();
    }
    format!("[\n{}\n]", markup(text))
}

fn optional_content(text: Option<&str>) -> String {
    match text.map(str::trim).filter(|text| !text.is_empty()) {
        Some(text) => content(text),
        None => "none".to_owned(),
    }
}

fn optional(value: Option<impl Display>) -> String {
    value.map_or_else(|| "none".to_owned(), |value| value.to_string())
}

fn paper_source(paper: &Paper) -> String {
    let mut out = paper_preamble();
    let _ = write!(
        out,
        "\n#show: paper.with(\n  \
         title: {},\n  \
         source: {},\n  \
         board: {},\n  \
         year: {},\n  \
         time-minutes: {},\n  \
         total-marks: {},\n  \
         instructions: {},\n)\n",
        quoted(&paper.title),
        literal(paper.source.as_deref()),
        literal(paper.board.as_deref()),
        optional(paper.year),
        optional(paper.time_minutes),
        optional(paper.total_marks),
        optional_content(paper.instructions.as_deref()),
    );
    questions(&mut out, &paper.questions);
    out
}

fn worksheet_source(worksheet: &Worksheet) -> String {
    let mut out = worksheet_preamble();
    let _ = write!(
        out,
        "\n#show: worksheet.with(\n  \
         title: {},\n  \
         student: {},\n  \
         due: {},\n  \
         intro: {},\n)\n",
        quoted(&worksheet.title),
        literal(worksheet.student.as_deref()),
        literal(worksheet.due.as_deref()),
        optional_content(worksheet.intro.as_deref()),
    );
    questions(&mut out, &worksheet.questions);
    out
}

/// One question on an auto-height page the width of a paper's text column, through the same
/// helpers a paper uses, so the app shows it exactly as it will be printed.
fn question_source(question: &Question, scheme: Option<&MarkSchemeQuestion>) -> String {
    let mut out = fragment_preamble();
    out.push_str("\n#show: fragment\n");
    questions(&mut out, std::slice::from_ref(question));
    if let Some(scheme) = scheme {
        scheme_question(&mut out, scheme);
    }
    out
}

fn markup_source(fragment: &Markup) -> String {
    let mut out = fragment_preamble();
    let _ = write!(
        out,
        "\n#show: fragment\n\n{}\n",
        markup(fragment.text.trim()),
    );
    out
}

fn questions(out: &mut String, questions: &[Question]) {
    for question in questions {
        let _ = write!(
            out,
            "\n#paper-question({}, {}){}\n",
            quoted(&question.number),
            optional(question.marks),
            content(question.stem.as_deref().unwrap_or_default()),
        );
        answerlines(out, question.answer_lines, 0);
        for part in &question.parts {
            part_source(out, part, 1);
        }
    }
}

fn part_source(out: &mut String, part: &Part, depth: usize) {
    let helper = if depth == 1 { "part" } else { "subpart" };
    let _ = writeln!(
        out,
        "#{helper}({}, {}){}",
        quoted(&part.label),
        optional(part.marks),
        content(&part.text),
    );
    answerlines(out, part.answer_lines, depth);
    for part in &part.parts {
        part_source(out, part, depth + 1);
    }
}

/// The indent comes from the template's own `part-indent`, so the ruled lines line up with
/// whatever the layout chose.
fn answerlines(out: &mut String, lines: Option<u32>, depth: usize) {
    let Some(lines) = lines.filter(|lines| *lines > 0) else {
        return;
    };
    match depth {
        0 => {
            let _ = writeln!(out, "#answerlines({lines})");
        }
        1 => {
            let _ = writeln!(out, "#answerlines({lines}, indent: part-indent)");
        }
        _ => {
            let _ = writeln!(out, "#answerlines({lines}, indent: part-indent * {depth})");
        }
    }
}

fn mark_scheme_source(scheme: &MarkScheme) -> String {
    let mut out = mark_scheme_preamble();
    let _ = write!(
        out,
        "\n#show: mark-scheme.with(\n  title: {},\n)\n",
        quoted(&scheme.title),
    );
    for question in &scheme.questions {
        scheme_question(&mut out, question);
    }
    out
}

fn scheme_question(out: &mut String, question: &MarkSchemeQuestion) {
    let _ = write!(out, "\n#scheme-question({})[\n", quoted(&question.number));
    scheme_rows(out, question);
    out.push_str("]\n");
}

fn scheme_rows(out: &mut String, question: &MarkSchemeQuestion) {
    if question.answer.is_some() || question.notes.is_some() {
        let _ = write!(
            out,
            "#scheme-row(none, none)[\n{}\n]\n",
            body(question.answer.as_deref(), question.notes.as_deref()),
        );
    }
    for part in &question.parts {
        let _ = write!(
            out,
            "#scheme-row({}, {})[\n{}\n]\n",
            quoted(&part.label),
            optional(part.marks),
            body(Some(&part.answer), part.notes.as_deref()),
        );
    }
}

fn body(answer: Option<&str>, notes: Option<&str>) -> String {
    let mut out = String::new();
    if let Some(answer) = answer.map(str::trim).filter(|answer| !answer.is_empty()) {
        out.push_str(&markup(answer));
    }
    if let Some(notes) = notes.map(str::trim).filter(|notes| !notes.is_empty()) {
        if !out.is_empty() {
            out.push('\n');
        }
        let _ = write!(out, "#scheme-note[\n{}\n]", markup(notes));
    }
    out
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used, clippy::panic)]

    use super::markup;

    #[test]
    fn a_field_cannot_close_its_content_block_or_start_code() {
        assert_eq!(markup("a ] b"), "a \\] b");
        assert_eq!(markup("#let x = 1"), "\\#let x = 1");
        assert_eq!(markup("back \\] slash"), "back \\\\\\] slash");
        assert_eq!(markup("a // b"), "a \\// b");
        assert_eq!(markup("a /* b"), "a \\/* b");
    }

    #[test]
    fn maths_and_emphasis_survive() {
        assert_eq!(
            markup("*Solve* $x^2 - 5x + 6 = 0$"),
            "*Solve* $x^2 - 5x + 6 = 0$"
        );
    }
}
