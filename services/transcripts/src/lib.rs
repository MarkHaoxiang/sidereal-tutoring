//! The transcripts worker: an HTTP health endpoint and a poll loop over Directus.
//!
//! Nothing here transcribes. The loop reports what is waiting and leaves every document
//! `pending`; the transcription backend is a later decision.

mod documents;
mod health;
mod poll;

pub use documents::{COLLECTION, PendingTranscript, pending_transcripts};
pub use health::router;
pub use poll::{poll_loop, poll_once};
