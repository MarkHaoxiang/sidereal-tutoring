//! The figure bytes a render request carries. They live in memory for the length of one
//! request, are keyed by name with no path of any kind, and never touch a disk.

use std::collections::BTreeMap;

use base64::Engine as _;
use base64::alphabet;
use base64::engine::{DecodePaddingMode, GeneralPurpose, GeneralPurposeConfig};

/// The largest one figure may be, decoded.
pub const MAX_ASSET_BYTES: usize = 2 * 1024 * 1024;

/// The largest every figure in one request may be, decoded.
pub const MAX_ASSETS_BYTES: usize = 8 * 1024 * 1024;

/// The longest an asset name may be.
pub const MAX_ASSET_NAME: usize = 128;

/// Typst reads the format from the name, so only the ones it decodes are accepted.
const EXTENSIONS: [&str; 4] = ["png", "jpg", "jpeg", "svg"];

/// Padding is optional because encoders disagree about it and nothing here depends on it.
const BASE64: GeneralPurpose = GeneralPurpose::new(
    &alphabet::STANDARD,
    GeneralPurposeConfig::new().with_decode_padding_mode(DecodePaddingMode::Indifferent),
);

/// The decoded figures of one request, in memory only.
#[derive(Debug, Default)]
pub struct Assets {
    files: BTreeMap<String, Vec<u8>>,
}

/// Why a set of assets was refused. A name or an encoding is the caller's mistake at a path;
/// a size is a limit, answered with a 413.
#[derive(Debug)]
pub enum AssetError {
    Rejected { name: String, message: String },
    TooLarge { message: String },
}

impl Assets {
    /// Decodes `raw`, a map of asset name to standard base64. Whitespace inside a value and a
    /// leading `data:…;base64,` prefix are ignored, so a browser's `FileReader` output works
    /// unedited.
    pub fn decode(raw: &BTreeMap<String, String>) -> Result<Self, AssetError> {
        let mut files = BTreeMap::new();
        let mut total = 0usize;
        for (name, encoded) in raw {
            check_name(name)?;
            let encoded: String = encoded
                .rsplit_once(";base64,")
                .map_or(encoded.as_str(), |(_, payload)| payload)
                .chars()
                .filter(|character| !character.is_ascii_whitespace())
                .collect();
            if encoded.len() / 4 * 3 > MAX_ASSET_BYTES {
                return Err(too_large(name, encoded.len() / 4 * 3));
            }
            let bytes = BASE64
                .decode(&encoded)
                .map_err(|error| AssetError::Rejected {
                    name: name.clone(),
                    message: format!("not base64: {error}"),
                })?;
            if bytes.len() > MAX_ASSET_BYTES {
                return Err(too_large(name, bytes.len()));
            }
            total = total.saturating_add(bytes.len());
            if total > MAX_ASSETS_BYTES {
                return Err(AssetError::TooLarge {
                    message: format!(
                        "the assets are over {MAX_ASSETS_BYTES} bytes decoded, the limit for one request"
                    ),
                });
            }
            files.insert(name.clone(), bytes);
        }
        Ok(Self { files })
    }

    pub fn contains(&self, name: &str) -> bool {
        self.files.contains_key(name)
    }

    pub fn is_empty(&self) -> bool {
        self.files.is_empty()
    }

    pub fn iter(&self) -> impl Iterator<Item = (&str, &[u8])> {
        self.files
            .iter()
            .map(|(name, bytes)| (name.as_str(), bytes.as_slice()))
    }
}

fn too_large(name: &str, bytes: usize) -> AssetError {
    AssetError::TooLarge {
        message: format!("the asset \"{name}\" is {bytes} bytes; the limit is {MAX_ASSET_BYTES}"),
    }
}

/// A name, never a path: the resolver has nothing to resolve against, and a name that could be
/// read as one is refused rather than quietly flattened.
fn check_name(name: &str) -> Result<(), AssetError> {
    let reject = |message: &str| {
        Err(AssetError::Rejected {
            name: name.to_owned(),
            message: message.to_owned(),
        })
    };
    if name.is_empty() || name.len() > MAX_ASSET_NAME {
        return reject(&format!("a name is 1 to {MAX_ASSET_NAME} characters"));
    }
    if name.starts_with('.')
        || !name.chars().all(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '.' | '-' | '_')
        })
    {
        return reject(
            "a name is letters, digits, dot, dash and underscore only, and is not a path",
        );
    }
    let extension = name
        .rsplit_once('.')
        .map(|(_, extension)| extension.to_ascii_lowercase());
    match extension {
        Some(extension) if EXTENSIONS.contains(&extension.as_str()) => Ok(()),
        _ => reject(&format!(
            "the name must end in one of {}, which is how the format is read",
            EXTENSIONS.join(", ")
        )),
    }
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used, clippy::panic)]

    use std::collections::BTreeMap;

    use super::{AssetError, Assets};

    fn raw(name: &str, value: &str) -> BTreeMap<String, String> {
        BTreeMap::from([(name.to_owned(), value.to_owned())])
    }

    #[test]
    fn a_name_that_is_a_path_or_has_no_known_extension_is_refused() {
        for name in ["../secret.png", "figures/one.png", "one.gif", ".one.png"] {
            let error = Assets::decode(&raw(name, "AA==")).unwrap_err();
            assert!(matches!(error, AssetError::Rejected { .. }), "{name}");
        }
    }

    #[test]
    fn whitespace_and_a_data_uri_prefix_are_ignored() {
        let assets = Assets::decode(&raw("one.png", "data:image/png;base64,QU\nJD")).unwrap();
        assert_eq!(assets.iter().next(), Some(("one.png", b"ABC".as_slice())));
    }
}
