/// The house templates, shipped in the binary. A rendered source is a template followed by a
/// `#show:` line and a body, so the result needs no other file.
const HOMEWORK: &str = include_str!("../template/homework.typ");
const QUESTIONS: &str = include_str!("../template/questions.typ");
const PAPER: &str = include_str!("../template/paper.typ");
const MARK_SCHEME: &str = include_str!("../template/mark_scheme.typ");
const WORKSHEET: &str = include_str!("../template/worksheet.typ");

pub fn wrap_homework(title: &str, student: Option<&str>, due: Option<&str>, body: &str) -> String {
    format!(
        "{HOMEWORK}\n#show: homework.with(\n  title: {},\n  student: {},\n  due: {},\n)\n\n{}\n",
        literal(Some(title)),
        literal(student),
        literal(due),
        body.trim_end()
    )
}

pub(crate) fn paper_preamble() -> String {
    format!("{QUESTIONS}\n{PAPER}")
}

pub(crate) fn worksheet_preamble() -> String {
    format!("{QUESTIONS}\n{WORKSHEET}")
}

pub(crate) fn mark_scheme_preamble() -> String {
    MARK_SCHEME.to_owned()
}

/// A Typst string literal, or `none` for an absent value.
pub(crate) fn literal(value: Option<&str>) -> String {
    match value.filter(|value| !value.is_empty()) {
        Some(value) => quoted(value),
        None => "none".to_owned(),
    }
}

/// A Typst string literal. No input can close it: the quote and the backslash are the only
/// characters that could, and both are escaped.
pub(crate) fn quoted(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for character in value.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ => out.push(character),
        }
    }
    out.push('"');
    out
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used, clippy::panic)]

    use super::{literal, wrap_homework};

    #[test]
    fn absent_and_empty_values_become_none() {
        assert_eq!(literal(None), "none");
        assert_eq!(literal(Some("")), "none");
    }

    #[test]
    fn a_quote_in_a_title_cannot_close_the_literal() {
        let wrapped = wrap_homework("Newton\"s \\ laws", None, None, "body");
        assert!(
            wrapped.contains(r#"title: "Newton\"s \\ laws""#),
            "{wrapped}"
        );
    }
}
