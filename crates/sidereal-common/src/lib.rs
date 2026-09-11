//! What every Sidereal service does before it does anything of its own: read its address and its
//! Directus credentials out of the environment, and install a tracing subscriber.

mod config;
mod tracing_setup;

pub use config::{
    ConfigError, DIRECTUS_TOKEN, DIRECTUS_URL, DirectusConfig, bind_addr_from_env,
    directus_from_env, secs_from_env,
};
pub use tracing_setup::init_tracing;
