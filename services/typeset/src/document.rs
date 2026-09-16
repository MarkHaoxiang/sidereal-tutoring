//! The canonical document structures. Deserialization is strict: an unknown field is an
//! error, so a typo in a generated document is reported rather than silently dropped.

use serde::{Deserialize, Serialize};

/// The most ruled answer lines one field may ask for; a page holds about thirty-five.
pub const MAX_ANSWER_LINES: u32 = 60;

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
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Question {
    pub number: String,
    pub stem: Option<String>,
    pub marks: Option<u32>,
    #[serde(default)]
    pub parts: Vec<Part>,
    pub answer_lines: Option<u32>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Part {
    pub label: String,
    pub text: String,
    pub marks: Option<u32>,
    pub answer_lines: Option<u32>,
    #[serde(default)]
    pub parts: Vec<Part>,
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
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MarkSchemePart {
    pub label: String,
    pub answer: String,
    pub marks: Option<u32>,
    pub notes: Option<String>,
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

impl Document {
    pub fn validate(&self) -> Vec<ValidationError> {
        let mut errors = Vec::new();
        match self {
            Self::Paper(paper) => questions(&paper.questions, &mut errors),
            Self::Worksheet(worksheet) => questions(&worksheet.questions, &mut errors),
            Self::Question { question, .. } => question_errors(question, "", &mut errors),
            Self::MarkScheme(_) | Self::Markup(_) => {}
        }
        errors
    }
}

fn questions(questions: &[Question], errors: &mut Vec<ValidationError>) {
    for (index, question) in questions.iter().enumerate() {
        question_errors(question, &format!("questions[{index}]"), errors);
    }
}

/// `root` is empty for a question sent on its own, so a fragment's errors are addressed the way
/// the fragment is indexed: `parts[0].answer_lines`, not `questions[0].parts[0].answer_lines`.
fn question_errors(question: &Question, root: &str, errors: &mut Vec<ValidationError>) {
    answer_lines(question.answer_lines, root, errors);
    for (index, part) in question.parts.iter().enumerate() {
        let path = field(root, &format!("parts[{index}]"));
        answer_lines(part.answer_lines, &path, errors);
        for (index, part) in part.parts.iter().enumerate() {
            let path = field(&path, &format!("parts[{index}]"));
            answer_lines(part.answer_lines, &path, errors);
            if !part.parts.is_empty() {
                errors.push(ValidationError::new(
                    field(&path, "parts"),
                    "parts nest one level only: a part of a part has no parts of its own",
                ));
            }
        }
    }
}

fn field(path: &str, name: &str) -> String {
    if path.is_empty() {
        name.to_owned()
    } else {
        format!("{path}.{name}")
    }
}

fn answer_lines(lines: Option<u32>, path: &str, errors: &mut Vec<ValidationError>) {
    if lines.is_some_and(|lines| lines > MAX_ANSWER_LINES) {
        errors.push(ValidationError::new(
            field(path, "answer_lines"),
            format!("at most {MAX_ANSWER_LINES} ruled lines"),
        ));
    }
}
