# Discord runtime

Pycord remains the single Discord library. Gateway events are normalized before the application layer
and live mention responses converge on the canonical intelligence pipeline. Existing allowlists,
observation modes, send gates, duplicate protection and 2,000-character delivery limit remain active.
Live slash-command, persistent-view and modal validation requires Discord credentials and a test guild;
those platform validations remain credential blocked and are not claimed here.

## Command audit

| Command | Use case | Permission/tenant | Side effect and safety |
| --- | --- | --- | --- |
| `/noesis_ping` | Gateway response | Guild/DM | No side effect; public response |
| `/noesis_chat` | Host conversation turn | Allowed channel/guild | Deferred response; canonical host flow |
| `/noesis_announce` | Format announcement | Allowed channel/guild | No publishing; formatting only |
| `/noesis_plan` | Persist episode plan | Allowed channel/guild | Structured write; deferred response |
| `/noesis_solo` | Start configured live session | Allowed channel/guild | Side effect; runtime errors are safe |
| `/noesis_voice_test` | Configured voice diagnostic | Allowed channel/guild | Side effect; hardware/credential blocked |
| `/noesis_nft` | Existing research insight | Allowed channel/guild | Provider limitations surfaced |
| `/noesis_status` | Construction status | Guild/DM | No side effect; no live-readiness claim |
| `/noesis_memory_correct` | Typed correction modal | Allowed channel/guild/user | Ephemeral, moderated, idempotent record |

Commands do not use LLM-backed autocomplete. Cancellation is provided for persistent side-effect
confirmations rather than long-running command inference. Live command behavior remains guild blocked.
