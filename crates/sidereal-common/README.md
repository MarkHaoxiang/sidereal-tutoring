# sidereal-common

```rust,ignore
use sidereal_common::{bind_addr_from_env, directus_from_env, init_tracing, secs_from_env};

init_tracing();
let addr = bind_addr_from_env("SIDEREAL_TRANSCRIPTS_ADDR", "127.0.0.1:50051")?;
let poll = secs_from_env("SIDEREAL_TRANSCRIPTS_POLL_SECS", 30)?;
let directus = directus_from_env()?; // SIDEREAL_DIRECTUS_URL, SIDEREAL_DIRECTUS_TOKEN
```

`RUST_LOG` filters the log; it defaults to `info`.

```sh
cargo test -p sidereal-common
```
