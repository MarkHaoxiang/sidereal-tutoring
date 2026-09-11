//! A typed async client for Directus's `/items/<collection>` REST API.
//!
//! Every response is unwrapped from Directus's `{"data": ...}` envelope, and every non-2xx
//! response becomes [`Error::Api`] carrying the status and Directus's own `errors[]` messages.

mod client;
mod error;
mod query;

pub use client::Client;
pub use error::Error;
pub use query::Query;
