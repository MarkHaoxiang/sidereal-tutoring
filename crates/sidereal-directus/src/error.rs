use reqwest::StatusCode;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("{base_url} cannot be a Directus base URL")]
    BaseUrl { base_url: String },

    #[error("building the HTTP client failed")]
    Client(#[source] reqwest::Error),

    #[error("the Directus request failed")]
    Transport(#[from] reqwest::Error),

    #[error("Directus returned {status}: {}", summarise(.messages))]
    Api {
        status: StatusCode,
        messages: Vec<String>,
    },

    #[error("decoding the Directus response body failed")]
    Decode(#[from] serde_json::Error),
}

impl Error {
    /// The HTTP status, for the responses that carried one.
    #[must_use]
    pub fn status(&self) -> Option<StatusCode> {
        match self {
            Self::Api { status, .. } => Some(*status),
            Self::Transport(error) => error.status(),
            _ => None,
        }
    }
}

/// Directus answers some failures (a bad token on a public route, a proxy in front of it) with
/// no `errors[]` at all, so the status has to carry the whole message.
fn summarise(messages: &[String]) -> String {
    if messages.is_empty() {
        "no message".to_owned()
    } else {
        messages.join("; ")
    }
}
