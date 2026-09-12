# roles

Empty by design. Schema snapshots carry collections, fields and relations only — not roles,
policies or permissions — so the `Tutor` and `Student` roles, their policies and the
`agent@sidereal.example.com` service account are created by `scripts/directus-bootstrap.sh`
instead.

Both roles' scoping needs the licensed `custom_permission_rules_enabled` entitlement. Without
it the bootstrap creates the roles and policies and warns: a student is granted nothing, and a
tutor is granted everything, unscoped.
