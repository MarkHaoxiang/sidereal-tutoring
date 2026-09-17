# roles

Empty by design. Schema snapshots carry collections, fields and relations only — not roles,
policies or permissions — so the `Tutor` and `Student` roles, their policies and the
`agent@sidereal.example.com` service account are created by `scripts/directus-bootstrap.sh`
instead.

A third policy, `Service`, is attached to that service account directly rather than to a role,
so it widens the account and no tutor. It grants one row — `directus_users` read over `id`,
`email` and `status`, unfiltered — which is what `POST /api/auth/status` answers a refused
sign-in from. The account keeps its `Tutor` role alongside it.

Both roles' scoping needs the licensed `custom_permission_rules_enabled` entitlement. Without
it the bootstrap creates the roles and policies and warns: a student is granted nothing, and a
tutor is granted everything, unscoped.
