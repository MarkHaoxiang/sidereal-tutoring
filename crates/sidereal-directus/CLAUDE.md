# sidereal-directus — invariants

A typed client for `/items/<collection>`. No domain types: the caller supplies `T`.

## Invariants

- **Every response is unwrapped from the `{"data": ...}` envelope.** No caller sees the envelope.
- **Non-2xx is never a decode error.** It becomes `Error::Api` carrying the `StatusCode` and
  Directus's `errors[].message`; a body that is not Directus's error shape yields no messages
  rather than masking the status.
- **Collections and ids go in as path segments, never interpolated into a URL string**, so they
  are percent-encoded and cannot escape the path.
- **Tests never touch the network.** They run against a `wiremock` stub.
