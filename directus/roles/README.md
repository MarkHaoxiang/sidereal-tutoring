# roles

Empty by design. Schema snapshots carry collections, fields and relations only — not roles,
policies or permissions — so the `Tutor` and `Student` roles, their policies and the
`agent@sidereal.example.com` service account are created by `scripts/directus-bootstrap.sh`
instead.

The `Student` grants need the licensed `custom_permission_rules_enabled` entitlement; without
it the bootstrap creates the role and policy, warns, and grants a student nothing.
