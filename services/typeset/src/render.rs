//! Structure to Typst markup. Layout lives in `template/`; this module only decides which
//! helper each node calls and how a tutor's text is made safe to place inside `[ ]`.

use std::collections::BTreeMap;
use std::fmt::Display;
use std::fmt::Write as _;

use crate::document::{
    Answer, AnswerKind, Block, Document, MarkScheme, MarkSchemeQuestion, Markup, Paper, Part,
    Passage, Question, Section, Worksheet,
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
/// inside a helper's `[ ]` block. `escape` makes the prose safe, `line_breaks` keeps its own
/// lines, and `balance` closes the delimiters it left open.
fn markup(text: &str) -> String {
    balance(&line_breaks(&escape(text)))
}

/// Four characters could leave the content block or start code, so each is escaped: the
/// backslash first (or it would re-arm the others), then `#`, `[` and `]`. `/` is escaped only
/// where it would open a comment. The emitted block is therefore always balanced and never
/// executes: a field cannot call a Typst function, and layout stays the template's job.
///
/// Four more are syntax that ordinary prose walks into. Outside a `$…$` span, `<` opens a
/// label (`a <3 b` is an unclosed label, and `<name>` silently becomes one), `>` closes it,
/// `@` is a reference (`email@example.com` names a label that does not exist) and a backtick
/// opens raw text. All four are escaped, so prose prints as prose; inside maths they are
/// operators and are left alone.
///
/// `/` is escaped in three more places: after a `*`, where it would end a block comment that
/// never began, and at the start of a line, where `/ term` opens a term list and is an error
/// without its colon. A line may therefore start with `- `, `+ ` or `1. ` and still be a list,
/// but not with `/ `.
///
/// Markup that is merely wrong — an unclosed `$`, say — still reaches the compiler and comes
/// back as a diagnostic.
fn escape(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut characters = text.chars().peekable();
    let mut maths = false;
    let mut previous = None;
    let mut starting = true;
    while let Some(character) = characters.next() {
        let after = characters.peek().copied();
        let opens_a_term = starting && matches!(after, None | Some(' ' | '\t' | '\n' | '\r'));
        match character {
            '\\' | '#' | '[' | ']' => {
                out.push('\\');
                out.push(character);
            }
            '/' if matches!(after, Some('/' | '*')) || previous == Some('*') || opens_a_term => {
                out.push_str("\\/");
            }
            '<' | '>' | '@' | '`' if !maths => {
                out.push('\\');
                out.push(character);
            }
            // No `$` is ever added or removed, so this tracks exactly what the compiler sees.
            '$' => {
                maths = !maths;
                out.push('$');
            }
            '\r' if after == Some('\n') => {}
            _ => out.push(character),
        }
        starting = character == '\n' || (starting && matches!(character, ' ' | '\t' | '\r'));
        previous = Some(character);
    }
    out
}

/// One newline becomes `\` at the end of the line — Typst's line break — and a run of blank
/// lines becomes one paragraph break. A line that opens a list or a heading is left alone:
/// Typst already starts those on their own line, and a break before one would print an empty
/// line inside the list.
fn line_breaks(text: &str) -> String {
    let lines: Vec<&str> = text.split('\n').map(str::trim_end).collect();
    let mut out = String::with_capacity(text.len() + lines.len());
    let mut blank = false;
    for line in lines {
        if line.is_empty() {
            blank = !out.is_empty();
            continue;
        }
        if !out.is_empty() {
            if blank {
                out.push_str("\n\n");
            } else if opens_a_block(line) {
                out.push('\n');
            } else {
                out.push_str("\\\n");
            }
        }
        blank = false;
        out.push_str(line);
    }
    out
}

/// `*` and `_` are delimiters that must close, innermost first, before the block they opened
/// in ends — so a stray one (`a * b`, `sep_ate*`) or a crossed pair (`*a _b* c_`) is a compile
/// error rather than a printed character. They are paired here exactly as the compiler pairs
/// them, and every one left open, or closing something that is not innermost, is escaped. A
/// pair is left alone, so `*bold*` and `_emph_` still mean what they said.
fn balance(text: &str) -> String {
    let mut escapes = Vec::new();
    let mut open: Vec<(char, usize)> = Vec::new();
    let mut maths = false;
    let mut escaped = false;
    let mut previous = None;
    let mut characters = text.char_indices().peekable();
    while let Some((index, character)) = characters.next() {
        let before = previous;
        previous = Some(character);
        if escaped {
            escaped = false;
            continue;
        }
        let after = characters.peek().map(|(_, character)| *character);
        match character {
            '\\' => escaped = true,
            '$' => maths = !maths,
            // Every newline this scan reaches starts a new block — a blank line is a paragraph
            // and a bare one precedes a list item or a heading — and a new block closes
            // everything the last one left open. A line break is `\` and a newline, whose
            // newline the escape above has already stepped over.
            '\n' => close(&mut open, &mut escapes),
            '*' | '_' if !maths && !in_word(before, after) => {
                match open.last() {
                    Some((delimiter, _)) if *delimiter == character => {
                        open.pop();
                    }
                    // Closing one that is not the innermost: the compiler refuses to cross.
                    _ if open.iter().any(|(delimiter, _)| *delimiter == character) => {
                        escapes.push(index);
                    }
                    _ => open.push((character, index)),
                }
            }
            _ => {}
        }
    }
    close(&mut open, &mut escapes);
    if escapes.is_empty() {
        return text.to_owned();
    }

    escapes.sort_unstable();
    let mut out = String::with_capacity(text.len() + escapes.len());
    let mut done = 0;
    for index in escapes {
        out.push_str(text.get(done..index).unwrap_or_default());
        out.push('\\');
        done = index;
    }
    out.push_str(text.get(done..).unwrap_or_default());
    out
}

fn close(open: &mut Vec<(char, usize)>, escapes: &mut Vec<usize>) {
    escapes.extend(open.drain(..).map(|(_, index)| index));
}

/// A `*` or `_` with a letter or a digit on both sides is part of the word, not a delimiter:
/// `snake_case` and `a*b*c` print as they are written and need no closing. This is the
/// compiler's own test, so counting only the delimiters counts what it counts.
fn in_word(before: Option<char>, after: Option<char>) -> bool {
    before.is_some_and(char::is_alphanumeric) && after.is_some_and(char::is_alphanumeric)
}

/// Whether a line starts a Typst block that is already set on a line of its own: `- item`,
/// `+ item`, `1. item`, `= heading`. A term list is not one: `escape` has already escaped the
/// `/` that would open it.
fn opens_a_block(line: &str) -> bool {
    let line = line.trim_start();
    let rest = line.trim_start_matches(['-', '+', '=']);
    if rest.len() < line.len() {
        return rest.is_empty() || rest.starts_with(' ');
    }
    let digits = line.trim_start_matches(|character: char| character.is_ascii_digit());
    digits.len() < line.len() && digits.starts_with(". ")
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

/// The paper-level passages a `passage_ref` block can name, by id. A worksheet or a fragment
/// has none; validation has already refused any reference that would not resolve.
type Passages<'a> = BTreeMap<&'a str, &'a Passage>;

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

    let passages: Passages<'_> = paper
        .passages
        .iter()
        .map(|passage| (passage.id.as_str(), passage))
        .collect();
    for passage in &paper.passages {
        let _ = write!(
            out,
            "\n#passage-block({}, {})\n",
            optional_content(passage.title.as_deref()),
            quoted(passage.text.trim_end()),
        );
    }

    questions(&mut out, &paper.questions, &passages);
    for section in &paper.sections {
        section_source(&mut out, section, &passages);
    }
    out
}

fn section_source(out: &mut String, section: &Section, passages: &Passages<'_>) {
    let _ = write!(
        out,
        "\n#section-heading({}, {}, {}, {})\n",
        optional_content(section.title.as_deref()),
        optional_content(section.instructions.as_deref()),
        optional(section.choose),
        optional(section_marks(section)),
    );
    questions(out, &section.questions, passages);
}

/// A section's own total. Where the student chooses, the answerable total is `choose` times
/// one question's marks — and only where every question is worth the same, since anything else
/// has no single answer. Nothing here touches the paper's `total_marks`.
fn section_marks(section: &Section) -> Option<u32> {
    let first = section.questions.first()?.marks?;
    let every = section
        .questions
        .iter()
        .map(|question| question.marks)
        .collect::<Option<Vec<u32>>>()?;
    match section.choose {
        Some(choose) if every.iter().all(|marks| *marks == first) => {
            Some(choose.saturating_mul(first))
        }
        Some(_) => None,
        None => Some(
            every
                .iter()
                .fold(0, |total, marks| total.saturating_add(*marks)),
        ),
    }
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
    questions(&mut out, &worksheet.questions, &Passages::new());
    out
}

/// One question on an auto-height page the width of a paper's text column, through the same
/// helpers a paper uses, so the app shows it exactly as it will be printed.
fn question_source(question: &Question, scheme: Option<&MarkSchemeQuestion>) -> String {
    let mut out = fragment_preamble();
    out.push_str("\n#show: fragment\n");
    questions(&mut out, std::slice::from_ref(question), &Passages::new());
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

fn questions(out: &mut String, questions: &[Question], passages: &Passages<'_>) {
    for question in questions {
        let _ = write!(
            out,
            "\n#paper-question({}, {}){}\n",
            quoted(&question.number),
            optional(question.marks),
            content(question.stem.as_deref().unwrap_or_default()),
        );
        blocks(out, &question.blocks, passages, 0);
        answer_source(out, question.answer_lines, question.answer.as_ref(), 0);
        for part in &question.parts {
            part_source(out, part, passages, 1);
        }
    }
}

fn part_source(out: &mut String, part: &Part, passages: &Passages<'_>, depth: usize) {
    let helper = if depth == 1 { "part" } else { "subpart" };
    let _ = writeln!(
        out,
        "#{helper}({}, {}){}",
        quoted(&part.label),
        optional(part.marks),
        content(&part.text),
    );
    blocks(out, &part.blocks, passages, depth);
    answer_source(out, part.answer_lines, part.answer.as_ref(), depth);
    for part in &part.parts {
        part_source(out, part, passages, depth + 1);
    }
}

/// The indent comes from the template's own `part-indent`, so an answer space and a block line
/// up with whatever the layout chose.
fn indent(depth: usize) -> String {
    match depth {
        0 => String::new(),
        1 => ", indent: part-indent".to_owned(),
        _ => format!(", indent: part-indent * {depth}"),
    }
}

/// `answer_lines` is the older spelling of `{"type": "lines"}` and emits the same call, so a
/// document written before answer types renders byte for byte as it did.
fn answer_source(out: &mut String, lines: Option<u32>, answer: Option<&Answer>, depth: usize) {
    if let Some(lines) = lines.filter(|lines| *lines > 0) {
        let _ = writeln!(out, "#answerlines({lines}{})", indent(depth));
    }
    let Some(answer) = answer else {
        return;
    };
    let indent = indent(depth);
    match answer.kind {
        AnswerKind::Lines => {
            let lines = answer.lines();
            if lines > 0 {
                let _ = writeln!(out, "#answerlines({lines}{indent})");
            }
        }
        AnswerKind::Boxed => {
            let _ = writeln!(out, "#answer-box({}mm{indent})", answer.height_mm());
        }
        AnswerKind::Essay => {
            let _ = writeln!(out, "#answer-essay({}mm{indent})", answer.height_mm());
        }
        AnswerKind::MultipleChoice => {
            let _ = write!(out, "#answer-choices((");
            for option in &answer.options {
                let _ = write!(
                    out,
                    "\n  (label: {}, body: {}),",
                    literal(option.label.as_deref()),
                    content(&option.text),
                );
            }
            let _ = writeln!(out, "\n){indent})");
        }
        AnswerKind::Grid => {
            let _ = writeln!(
                out,
                "#answer-grid({}, {}{indent})",
                optional(answer.rows),
                optional(answer.cols),
            );
        }
        AnswerKind::Table => {
            let _ = writeln!(
                out,
                "#answer-table({}, {}{indent})",
                optional(answer.rows),
                optional(answer.cols),
            );
        }
        AnswerKind::Nothing => {}
    }
}

fn blocks(out: &mut String, blocks: &[Block], passages: &Passages<'_>, depth: usize) {
    let indent = indent(depth);
    for block in blocks {
        match block {
            Block::Passage { title, text } => {
                let _ = writeln!(
                    out,
                    "#passage-block({}, {}{indent})",
                    optional_content(title.as_deref()),
                    quoted(text.trim_end()),
                );
            }
            Block::PassageRef { id } => {
                let title = passages
                    .get(id.as_str())
                    .and_then(|passage| passage.title.as_deref())
                    .unwrap_or(id);
                let _ = writeln!(out, "#passage-ref({}{indent})", content(title));
            }
            Block::Code { language, text } => {
                let _ = writeln!(
                    out,
                    "#code-block({}, {}{indent})",
                    literal(language.as_deref()),
                    quoted(text.trim_end()),
                );
            }
            Block::Table {
                caption,
                header,
                rows,
            } => {
                let _ = write!(
                    out,
                    "#data-table({}, {}, (",
                    optional_content(caption.as_deref()),
                    match header {
                        Some(header) => cells(header),
                        None => "none".to_owned(),
                    },
                );
                for row in rows {
                    let _ = write!(out, "\n  {},", cells(row));
                }
                let _ = writeln!(out, "\n){indent})");
            }
            Block::Figure {
                asset,
                caption,
                width_mm,
            } => {
                let _ = writeln!(
                    out,
                    "#figure-block({}, {}, {}{indent})",
                    quoted(asset),
                    optional_content(caption.as_deref()),
                    width_mm.map_or_else(|| "none".to_owned(), |width| format!("{width}mm")),
                );
            }
        }
    }
}

/// A Typst array of content, with the trailing comma a one-element array needs.
fn cells(cells: &[String]) -> String {
    let mut out = "(".to_owned();
    for cell in cells {
        let _ = write!(out, "{}, ", content(cell));
    }
    out.push(')');
    out
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
    if question.answer.is_some() || question.notes.is_some() || !question.blocks.is_empty() {
        let _ = write!(
            out,
            "#scheme-row(none, none)[\n{}\n]\n",
            body(
                question.answer.as_deref(),
                question.notes.as_deref(),
                &question.blocks,
            ),
        );
    }
    for part in &question.parts {
        let _ = write!(
            out,
            "#scheme-row({}, {})[\n{}\n]\n",
            quoted(&part.label),
            optional(part.marks),
            body(Some(&part.answer), part.notes.as_deref(), &part.blocks),
        );
    }
}

fn body(answer: Option<&str>, notes: Option<&str>, entries: &[Block]) -> String {
    let mut out = String::new();
    if let Some(answer) = answer.map(str::trim).filter(|answer| !answer.is_empty()) {
        out.push_str(&markup(answer));
    }
    if !entries.is_empty() {
        if !out.is_empty() {
            out.push('\n');
        }
        blocks(&mut out, entries, &Passages::new(), 0);
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
        assert_eq!(markup("a /* b"), "a \\/\\* b");
    }

    #[test]
    fn maths_and_emphasis_survive() {
        assert_eq!(
            markup("*Solve* $x^2 - 5x + 6 = 0$"),
            "*Solve* $x^2 - 5x + 6 = 0$"
        );
        assert_eq!(markup("a _b_ c"), "a _b_ c");
    }

    #[test]
    fn prose_that_looks_like_a_label_a_reference_or_raw_is_printed() {
        assert_eq!(markup("a < b and x > y"), "a \\< b and x \\> y");
        assert_eq!(markup("email@example.com"), "email\\@example.com");
        assert_eq!(markup("a ` backtick"), "a \\` backtick");
        // Inside maths they are operators, and the escape would be the error.
        assert_eq!(markup("$a < b$ and a < b"), "$a < b$ and a \\< b");
        assert_eq!(markup("$x >= 1$"), "$x >= 1$");
    }

    #[test]
    fn an_unclosed_delimiter_is_escaped_and_a_closed_one_is_not() {
        assert_eq!(markup("*unbalanced prose"), "\\*unbalanced prose");
        assert_eq!(markup("a *b* and *c"), "a *b* and \\*c");
        assert_eq!(markup("a * b"), "a \\* b");
        assert_eq!(markup("a _lone underscore"), "a \\_lone underscore");
        // A letter or a digit on both sides makes it part of the word, as it does for the
        // compiler, so it is neither counted nor escaped.
        assert_eq!(markup("snake_case_name"), "snake_case_name");
        assert_eq!(markup("a*b*c"), "a*b*c");
        assert_eq!(markup("_a_b_"), "_a_b_");
        assert_eq!(markup("a_b_c_d_e_"), "a_b_c_d_e\\_");
        assert_eq!(markup("sep_ate*"), "sep_ate\\*");
        // The compiler counts per paragraph, and not inside maths.
        assert_eq!(markup("*one\n\ntwo*"), "\\*one\n\ntwo\\*");
        assert_eq!(markup("$a * b$ and *bold*"), "$a * b$ and *bold*");
        assert_eq!(markup("$a_1$ and _loose"), "$a_1$ and \\_loose");
        // A crossed pair closes what is not innermost, which the compiler refuses.
        assert_eq!(markup("a *b _c* d_"), "a \\*b _c\\* d_");
        // A list item is its own block, so a delimiter cannot reach the next one.
        assert_eq!(markup("- one *a\n- two *b"), "- one \\*a\n- two \\*b");
    }

    #[test]
    fn a_slash_that_would_open_a_comment_or_a_term_list_is_escaped() {
        assert_eq!(markup("a */ b"), "a \\*\\/ b");
        assert_eq!(markup("/ no colon here"), "\\/ no colon here");
        assert_eq!(markup("a / b and 3/4"), "a / b and 3/4");
    }

    #[test]
    fn a_newline_is_a_line_break_and_a_blank_line_a_paragraph() {
        assert_eq!(markup("Tyger\nTyger"), "Tyger\\\nTyger");
        assert_eq!(markup("one\r\ntwo"), "one\\\ntwo");
        assert_eq!(markup("one\n\n\ntwo"), "one\n\ntwo");
        assert_eq!(markup("\n\none\n \n"), "one");
    }

    #[test]
    fn a_list_keeps_its_own_lines() {
        assert_eq!(markup("Do these:\n- one\n- two"), "Do these:\n- one\n- two");
        assert_eq!(markup("= Heading\nbody"), "= Heading\\\nbody");
        assert_eq!(markup("1. one\n2. two"), "1. one\n2. two");
    }
}
