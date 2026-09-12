/// The house template, shipped in the binary. `wrap_homework` returns it followed by the
/// `show` rule and the body, so the result is a complete document that needs no other file.
const HOMEWORK: &str = include_str!("../template/homework.typ");

pub fn wrap_homework(title: &str, student: Option<&str>, due: Option<&str>, body: &str) -> String {
    format!(
        "{HOMEWORK}\n#show: homework.with(\n  title: {},\n  student: {},\n  due: {},\n)\n\n{}\n",
        literal(Some(title)),
        literal(student),
        literal(due),
        body.trim_end()
    )
}

/// A Typst string literal, or `none` for an absent value.
fn literal(value: Option<&str>) -> String {
    let Some(value) = value.filter(|value| !value.is_empty()) else {
        return "none".to_owned();
    };
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
