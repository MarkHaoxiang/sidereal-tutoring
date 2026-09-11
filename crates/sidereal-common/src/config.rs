use std::net::{AddrParseError, SocketAddr};
use std::num::ParseIntError;
use std::time::Duration;

use thiserror::Error;

pub const DIRECTUS_URL: &str = "SIDEREAL_DIRECTUS_URL";
pub const DIRECTUS_TOKEN: &str = "SIDEREAL_DIRECTUS_TOKEN";

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("{var} is not set")]
    Missing { var: String },

    #[error("{var} is not a socket address: {value:?}")]
    NotAnAddr {
        var: String,
        value: String,
        #[source]
        source: AddrParseError,
    },

    #[error("{var} is not a whole number of seconds: {value:?}")]
    NotSeconds {
        var: String,
        value: String,
        #[source]
        source: ParseIntError,
    },
}

#[derive(Debug, Clone)]
pub struct DirectusConfig {
    pub url: String,
    pub token: String,
}

/// The address `var` names, or `default` when it is unset or empty.
pub fn bind_addr_from_env(var: &str, default: &str) -> Result<SocketAddr, ConfigError> {
    parse_addr(var, env(var), default)
}

/// The interval `var` names, or `default` seconds when it is unset or empty.
pub fn secs_from_env(var: &str, default: u64) -> Result<Duration, ConfigError> {
    parse_secs(var, env(var), default)
}

pub fn directus_from_env() -> Result<DirectusConfig, ConfigError> {
    Ok(DirectusConfig {
        url: required(DIRECTUS_URL)?,
        token: required(DIRECTUS_TOKEN)?,
    })
}

/// A variable set to the empty string is treated as unset — compose files and shell wrappers
/// produce empty values far more often than they mean them.
fn env(var: &str) -> Option<String> {
    std::env::var(var).ok().filter(|value| !value.is_empty())
}

fn required(var: &str) -> Result<String, ConfigError> {
    env(var).ok_or_else(|| ConfigError::Missing {
        var: var.to_owned(),
    })
}

fn parse_addr(var: &str, value: Option<String>, default: &str) -> Result<SocketAddr, ConfigError> {
    let value = value.unwrap_or_else(|| default.to_owned());
    value.parse().map_err(|source| ConfigError::NotAnAddr {
        var: var.to_owned(),
        value,
        source,
    })
}

fn parse_secs(var: &str, value: Option<String>, default: u64) -> Result<Duration, ConfigError> {
    let Some(value) = value else {
        return Ok(Duration::from_secs(default));
    };
    let secs: u64 = value.parse().map_err(|source| ConfigError::NotSeconds {
        var: var.to_owned(),
        value: value.clone(),
        source,
    })?;
    Ok(Duration::from_secs(secs))
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used, clippy::panic)]

    use super::{ConfigError, parse_addr, parse_secs};
    use std::time::Duration;

    const VAR: &str = "SIDEREAL_TRANSCRIPTS_ADDR";

    #[test]
    fn an_unset_addr_falls_back_to_the_default() {
        let addr = parse_addr(VAR, None, "127.0.0.1:50051").unwrap();
        assert_eq!(addr.port(), 50051);
        assert!(addr.ip().is_loopback());
    }

    #[test]
    fn a_set_addr_wins() {
        let addr = parse_addr(VAR, Some("0.0.0.0:8080".to_owned()), "127.0.0.1:50051").unwrap();
        assert_eq!(addr.to_string(), "0.0.0.0:8080");
    }

    #[test]
    fn an_ipv6_addr_parses() {
        let addr = parse_addr(VAR, Some("[::1]:50051".to_owned()), "127.0.0.1:50051").unwrap();
        assert_eq!(addr.port(), 50051);
    }

    #[test]
    fn a_bad_addr_names_the_variable_and_the_value() {
        let error = parse_addr(VAR, Some("50051".to_owned()), "127.0.0.1:50051").unwrap_err();
        assert!(matches!(error, ConfigError::NotAnAddr { .. }), "{error:?}");
        let message = error.to_string();
        assert!(message.contains(VAR), "{message}");
        assert!(message.contains("50051"), "{message}");
    }

    #[test]
    fn a_bad_default_is_an_error_not_a_panic() {
        assert!(parse_addr(VAR, None, "nonsense").is_err());
    }

    #[test]
    fn seconds_fall_back_and_parse() {
        assert_eq!(parse_secs("V", None, 30).unwrap(), Duration::from_secs(30));
        assert_eq!(
            parse_secs("V", Some("5".to_owned()), 30).unwrap(),
            Duration::from_secs(5)
        );
        assert_eq!(
            parse_secs("V", Some("0".to_owned()), 30).unwrap(),
            Duration::ZERO
        );
    }

    #[test]
    fn bad_seconds_are_an_error() {
        let error = parse_secs("V", Some("-1".to_owned()), 30).unwrap_err();
        assert!(matches!(error, ConfigError::NotSeconds { .. }), "{error:?}");
        assert!(parse_secs("V", Some("2m".to_owned()), 30).is_err());
    }
}
