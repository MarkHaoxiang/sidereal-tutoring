//! The canonical document structures. Deserialization is strict: an unknown field is an
//! error, so a typo in a generated document is reported rather than silently dropped.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

use crate::assets::Assets;

/// The most ruled answer lines one field may ask for; a page holds about thirty-five.
pub const MAX_ANSWER_LINES: u32 = 60;

/// The tallest answer space, in millimetres: an A4 page's text column is 251 mm.
pub const MAX_ANSWER_HEIGHT_MM: u32 = 250;

/// One option per letter of the alphabet.
pub const MAX_ANSWER_OPTIONS: usize = 26;

/// A 5 mm squared grid: 26 columns is 130 mm, inside the 166 mm text column.
pub const MAX_GRID_ROWS: u32 = 40;
pub const MAX_GRID_COLS: u32 = 26;

pub const MAX_TABLE_ROWS: usize = 40;
pub const MAX_TABLE_COLS: usize = 12;

/// The A4 text column, in millimetres.
pub const MAX_FIGURE_WIDTH_MM: u32 = 165;

/// What `{"type": "lines"}` means when it carries no count.
const DEFAULT_ANSWER_LINES: u32 = 4;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DocumentKind {
    Paper,
    MarkScheme,
    Worksheet,
    Question,
    Markup,
}

#[derive(Debug)]
pub enum Document {
    Paper(Paper),
    MarkScheme(MarkScheme),
    Worksheet(Worksheet),
    Question {
        question: Question,
        scheme: Option<MarkSchemeQuestion>,
    },
    Markup(Markup),
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Paper {
    pub title: String,
    pub source: Option<String>,
    pub board: Option<String>,
    pub year: Option<i32>,
    pub time_minutes: Option<u32>,
    pub total_marks: Option<u32>,
    pub instructions: Option<String>,
    #[serde(default)]
    pub questions: Vec<Question>,
    #[serde(default)]
    pub sections: Vec<Section>,
    #[serde(default)]
    pub passages: Vec<Passage>,
}

/// A run of questions under one heading. `choose` is how many of them the student answers.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Section {
    pub title: Option<String>,
    pub instructions: Option<String>,
    pub choose: Option<u32>,
    #[serde(default)]
    pub questions: Vec<Question>,
}

/// A paper-level insert — the extract booklet — printed once and referred to by `passage_ref`.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Passage {
    pub id: String,
    pub title: Option<String>,
    pub text: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Question {
    pub number: String,
    pub stem: Option<String>,
    pub marks: Option<u32>,
    #[serde(default)]
    pub parts: Vec<Part>,
    /// Deprecated: `{"type": "lines", "lines": n}` says the same thing.
    pub answer_lines: Option<u32>,
    pub answer: Option<Answer>,
    #[serde(default)]
    pub blocks: Vec<Block>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Part {
    pub label: String,
    pub text: String,
    pub marks: Option<u32>,
    /// Deprecated: `{"type": "lines", "lines": n}` says the same thing.
    pub answer_lines: Option<u32>,
    pub answer: Option<Answer>,
    #[serde(default)]
    pub blocks: Vec<Block>,
    #[serde(default)]
    pub parts: Vec<Part>,
}

/// The space a student writes in. `type` decides which of the other fields are read.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Answer {
    #[serde(rename = "type")]
    pub kind: AnswerKind,
    pub lines: Option<u32>,
    #[serde(default)]
    pub options: Vec<AnswerOption>,
    pub height_mm: Option<u32>,
    pub rows: Option<u32>,
    pub cols: Option<u32>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AnswerKind {
    Lines,
    #[serde(rename = "box")]
    Boxed,
    MultipleChoice,
    Essay,
    Grid,
    Table,
    #[serde(rename = "none")]
    Nothing,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AnswerOption {
    pub label: Option<String>,
    pub text: String,
}

/// Material set between a stem and its parts: an extract, a listing, a data table, a figure.
#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum Block {
    Passage {
        title: Option<String>,
        text: String,
    },
    /// Points at a `Paper.passages` entry, printed once at the start of the paper.
    PassageRef {
        id: String,
    },
    Code {
        language: Option<String>,
        text: String,
    },
    Table {
        caption: Option<String>,
        header: Option<Vec<String>>,
        #[serde(default)]
        rows: Vec<Vec<String>>,
    },
    Figure {
        asset: String,
        caption: Option<String>,
        width_mm: Option<u32>,
    },
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MarkScheme {
    pub title: String,
    #[serde(default)]
    pub questions: Vec<MarkSchemeQuestion>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MarkSchemeQuestion {
    pub number: String,
    #[serde(default)]
    pub parts: Vec<MarkSchemePart>,
    pub answer: Option<String>,
    pub notes: Option<String>,
    #[serde(default)]
    pub blocks: Vec<Block>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MarkSchemePart {
    pub label: String,
    pub answer: String,
    pub marks: Option<u32>,
    pub notes: Option<String>,
    #[serde(default)]
    pub blocks: Vec<Block>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Markup {
    pub text: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Worksheet {
    pub title: String,
    pub student: Option<String>,
    pub due: Option<String>,
    pub intro: Option<String>,
    #[serde(default)]
    pub questions: Vec<Question>,
}

impl Answer {
    /// The count `answerlines` is called with, once the defaults are filled in.
    pub fn lines(&self) -> u32 {
        self.lines.unwrap_or(DEFAULT_ANSWER_LINES)
    }

    /// Millimetres, once the default for the kind is filled in.
    pub fn height_mm(&self) -> u32 {
        self.height_mm.unwrap_or(match self.kind {
            AnswerKind::Essay => 230,
            _ => 40,
        })
    }
}

/// One reason a structurally valid document is still refused, addressed by the same dotted
/// and indexed path serde reports for a field it could not read.
#[derive(Debug, Clone, Serialize)]
pub struct ValidationError {
    pub path: String,
    pub message: String,
}

impl ValidationError {
    fn new(path: String, message: impl Into<String>) -> Self {
        Self {
            path,
            message: message.into(),
        }
    }
}

/// What the whole request offers a node: the figure bytes that came with it, and the ids of
/// the paper-level passages a `passage_ref` may point at.
struct Context<'a> {
    assets: &'a Assets,
    passages: BTreeSet<&'a str>,
}

impl Document {
    pub fn validate(&self, assets: &Assets) -> Vec<ValidationError> {
        let mut errors = Vec::new();
        let mut context = Context {
            assets,
            passages: BTreeSet::new(),
        };
        match self {
            Self::Paper(paper) => {
                for passage in &paper.passages {
                    context.passages.insert(passage.id.as_str());
                }
                questions(&paper.questions, "questions", &context, &mut errors);
                for (index, section) in paper.sections.iter().enumerate() {
                    let root = format!("sections[{index}]");
                    section_errors(section, &root, &context, &mut errors);
                }
            }
            Self::Worksheet(worksheet) => {
                questions(&worksheet.questions, "questions", &context, &mut errors);
            }
            Self::Question { question, scheme } => {
                question_errors(question, "", &context, &mut errors);
                if let Some(scheme) = scheme {
                    scheme_question_errors(scheme, "mark_scheme", &context, &mut errors);
                }
            }
            Self::MarkScheme(scheme) => {
                for (index, question) in scheme.questions.iter().enumerate() {
                    let root = format!("questions[{index}]");
                    scheme_question_errors(question, &root, &context, &mut errors);
                }
            }
            Self::Markup(_) => {}
        }
        errors
    }
}

fn section_errors(
    section: &Section,
    root: &str,
    context: &Context<'_>,
    errors: &mut Vec<ValidationError>,
) {
    match section.choose {
        Some(0) => errors.push(ValidationError::new(
            field(root, "choose"),
            "a section asks for at least one question",
        )),
        Some(choose) if choose as usize > section.questions.len() => {
            errors.push(ValidationError::new(
                field(root, "choose"),
                format!(
                    "the section offers {} questions, so {choose} cannot be chosen",
                    section.questions.len()
                ),
            ));
        }
        _ => {}
    }
    questions(
        &section.questions,
        &field(root, "questions"),
        context,
        errors,
    );
}

fn questions(
    questions: &[Question],
    root: &str,
    context: &Context<'_>,
    errors: &mut Vec<ValidationError>,
) {
    for (index, question) in questions.iter().enumerate() {
        question_errors(question, &format!("{root}[{index}]"), context, errors);
    }
}

/// `root` is empty for a question sent on its own, so a fragment's errors are addressed the way
/// the fragment is indexed: `parts[0].answer_lines`, not `questions[0].parts[0].answer_lines`.
fn question_errors(
    question: &Question,
    root: &str,
    context: &Context<'_>,
    errors: &mut Vec<ValidationError>,
) {
    answer_errors(
        question.answer_lines,
        question.answer.as_ref(),
        root,
        errors,
    );
    blocks_errors(&question.blocks, root, context, errors);
    for (index, part) in question.parts.iter().enumerate() {
        let path = field(root, &format!("parts[{index}]"));
        answer_errors(part.answer_lines, part.answer.as_ref(), &path, errors);
        blocks_errors(&part.blocks, &path, context, errors);
        for (index, part) in part.parts.iter().enumerate() {
            let path = field(&path, &format!("parts[{index}]"));
            answer_errors(part.answer_lines, part.answer.as_ref(), &path, errors);
            blocks_errors(&part.blocks, &path, context, errors);
            if !part.parts.is_empty() {
                errors.push(ValidationError::new(
                    field(&path, "parts"),
                    "parts nest one level only: a part of a part has no parts of its own",
                ));
            }
        }
    }
}

fn scheme_question_errors(
    question: &MarkSchemeQuestion,
    root: &str,
    context: &Context<'_>,
    errors: &mut Vec<ValidationError>,
) {
    blocks_errors(&question.blocks, root, context, errors);
    for (index, part) in question.parts.iter().enumerate() {
        let path = field(root, &format!("parts[{index}]"));
        blocks_errors(&part.blocks, &path, context, errors);
    }
}

fn field(path: &str, name: &str) -> String {
    if path.is_empty() {
        name.to_owned()
    } else {
        format!("{path}.{name}")
    }
}

fn answer_errors(
    lines: Option<u32>,
    answer: Option<&Answer>,
    path: &str,
    errors: &mut Vec<ValidationError>,
) {
    if lines.is_some_and(|lines| lines > MAX_ANSWER_LINES) {
        errors.push(ValidationError::new(
            field(path, "answer_lines"),
            format!("at most {MAX_ANSWER_LINES} ruled lines"),
        ));
    }
    let Some(answer) = answer else {
        return;
    };
    if lines.is_some() {
        errors.push(ValidationError::new(
            field(path, "answer_lines"),
            "answer_lines is the deprecated spelling of answer; send one or the other",
        ));
    }
    let path = field(path, "answer");
    match answer.kind {
        AnswerKind::Lines => {
            if answer.lines() > MAX_ANSWER_LINES {
                errors.push(ValidationError::new(
                    field(&path, "lines"),
                    format!("at most {MAX_ANSWER_LINES} ruled lines"),
                ));
            }
        }
        AnswerKind::Boxed | AnswerKind::Essay => {
            if answer.height_mm() > MAX_ANSWER_HEIGHT_MM {
                errors.push(ValidationError::new(
                    field(&path, "height_mm"),
                    format!("at most {MAX_ANSWER_HEIGHT_MM} mm, the height of a page's text"),
                ));
            }
        }
        AnswerKind::MultipleChoice => {
            if answer.options.is_empty() {
                errors.push(ValidationError::new(
                    field(&path, "options"),
                    "a multiple choice answer needs at least one option",
                ));
            }
            if answer.options.len() > MAX_ANSWER_OPTIONS {
                errors.push(ValidationError::new(
                    field(&path, "options"),
                    format!("at most {MAX_ANSWER_OPTIONS} options"),
                ));
            }
        }
        AnswerKind::Grid => {
            extent(answer.rows, MAX_GRID_ROWS, &field(&path, "rows"), errors);
            extent(answer.cols, MAX_GRID_COLS, &field(&path, "cols"), errors);
        }
        AnswerKind::Table => {
            extent(
                answer.rows,
                MAX_TABLE_ROWS as u32,
                &field(&path, "rows"),
                errors,
            );
            extent(
                answer.cols,
                MAX_TABLE_COLS as u32,
                &field(&path, "cols"),
                errors,
            );
        }
        AnswerKind::Nothing => {}
    }
}

fn extent(value: Option<u32>, max: u32, path: &str, errors: &mut Vec<ValidationError>) {
    match value {
        None => errors.push(ValidationError::new(
            path.to_owned(),
            "this answer type needs both rows and cols",
        )),
        Some(0) => errors.push(ValidationError::new(path.to_owned(), "at least one")),
        Some(value) if value > max => errors.push(ValidationError::new(
            path.to_owned(),
            format!("at most {max}"),
        )),
        Some(_) => {}
    }
}

fn blocks_errors(
    blocks: &[Block],
    root: &str,
    context: &Context<'_>,
    errors: &mut Vec<ValidationError>,
) {
    for (index, block) in blocks.iter().enumerate() {
        let path = field(root, &format!("blocks[{index}]"));
        match block {
            Block::Passage { .. } | Block::Code { .. } => {}
            Block::PassageRef { id } => {
                if !context.passages.contains(id.as_str()) {
                    errors.push(ValidationError::new(
                        field(&path, "id"),
                        format!("no passage with id \"{id}\" is in the paper's passages"),
                    ));
                }
            }
            Block::Table { header, rows, .. } => {
                table_errors(header.as_deref(), rows, &path, errors);
            }
            Block::Figure {
                asset, width_mm, ..
            } => {
                if !context.assets.contains(asset) {
                    errors.push(ValidationError::new(
                        field(&path, "asset"),
                        format!("no asset named \"{asset}\" was sent with this request"),
                    ));
                }
                if width_mm.is_some_and(|width| width == 0 || width > MAX_FIGURE_WIDTH_MM) {
                    errors.push(ValidationError::new(
                        field(&path, "width_mm"),
                        format!("between 1 and {MAX_FIGURE_WIDTH_MM} mm, the text column"),
                    ));
                }
            }
        }
    }
}

fn table_errors(
    header: Option<&[String]>,
    rows: &[Vec<String>],
    path: &str,
    errors: &mut Vec<ValidationError>,
) {
    let columns = match header {
        Some(header) if !header.is_empty() => header.len(),
        _ => match rows.first() {
            Some(row) if !row.is_empty() => row.len(),
            _ => {
                errors.push(ValidationError::new(
                    field(path, "rows"),
                    "a table needs a header or at least one row",
                ));
                return;
            }
        },
    };
    if columns > MAX_TABLE_COLS {
        errors.push(ValidationError::new(
            field(path, "header"),
            format!("at most {MAX_TABLE_COLS} columns"),
        ));
    }
    if rows.len() > MAX_TABLE_ROWS {
        errors.push(ValidationError::new(
            field(path, "rows"),
            format!("at most {MAX_TABLE_ROWS} rows"),
        ));
    }
    for (index, row) in rows.iter().enumerate() {
        if row.len() != columns {
            errors.push(ValidationError::new(
                field(path, &format!("rows[{index}]")),
                format!("{} cells where the table has {columns} columns", row.len()),
            ));
        }
    }
}
