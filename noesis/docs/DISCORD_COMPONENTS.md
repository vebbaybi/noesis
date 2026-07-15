# Discord components

`PersistentActionView` supports confirmation/cancellation, moderation review, memory retention/removal,
and failed-action retry. Each custom ID is versioned and includes only a component reference; the JSON
structured repository remains authoritative for tenant, user/role authorization, expiry, operation,
state, and idempotency. Pending views are reconstructed and registered when the bot is constructed.

`MemoryCorrectionModal` is the connected structured modal. It has stable bounded fields, resolves the
guild and user at the boundary, creates a typed correction request, runs inbound moderation, and stores
a pending operator-review record. Responses are ephemeral. Full submissions are not logged.

Live component and modal interaction remains Discord-credential blocked. Construction, persistence,
restart, authorization, expiry, duplicate-action and successful execution are covered locally.
