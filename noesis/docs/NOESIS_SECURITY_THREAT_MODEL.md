# Security Threat Model

Implemented controls include pre-cognition platform authorization, exact conversation scope, bounded platform-scoped replay suppression, reserved logging-key sanitization, secret redaction, local-only operator routes, credential-presence booleans, host-path suppression, deterministic memory scoping, sensitive memory rejection, and evidence/tool separation.

Retrieved text is untrusted. Model output cannot directly execute a tool or platform action; only application code can call registered tools and dispatchers. The current Discord metadata tool has no mutation capability.

Remaining threats requiring implementation before remote or production expansion: real operator authentication/CSRF/TLS, trusted-proxy policy, SQLite encryption/backup policy, SSRF-safe connector transport, attachment sandboxing, durable distributed replay protection, prompt-injection evaluation, audit retention, and poisoning review workflows.
