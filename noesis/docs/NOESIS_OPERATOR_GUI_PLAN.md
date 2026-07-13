# Noesis Operator GUI Plan

## Purpose and users

The operator interface is a local control surface, not Noesis's personality and not a public chat product. It serves the operator/admin running Noesis, developers testing normalized events, community managers reviewing safe activity, and—later—an operator supervising voice sessions.

Its job is to control, test, and observe the existing runtime; show configuration readiness without secret values; review drafts and dispatch results; and expose documentation and manual verification checklists.

## Brand assets

The current `logo/` pack contains `logo.png` and `logoos.png`. Both are PNG raster assets. `logo.png` is a square transparent-background The 1807 shark mark using cyan, electric blue, black, and pale blue. It works as the operator header mark and app icon but is not a standalone Noesis wordmark. The UI should use dark navy surfaces, cyan status accents, and blue actions derived from this asset.

Missing assets: a Noesis wordmark, monochrome light/dark SVG marks, favicon sizes, spacing/minimum-size guidance, accessible color tokens, and licensing/ownership metadata. Raster assets should not be stretched or used as tiny detailed icons.

## Implemented first slice

`GET /operator` is a local-only, dependency-free FastAPI HTML page. It displays the logo, safe runtime/configuration readiness, a platform-neutral dry-run mention form, result JSON, and an OpenAPI link. `GET /operator/status` exposes booleans and issue descriptions but never secret values. There are no live-send controls and no authentication claim.

This approach is recommended for the first phase because it reuses FastAPI, has no frontend build chain, works locally, is inexpensive to test, and keeps configuration values server-side. A separate frontend or desktop wrapper should wait until the workflows and authentication/deployment boundary are stable.

## Planned operator activities

### System dashboard

Show API health, runtime profile, local data path, feature flags, provider availability, local fallback, platform enabled/readiness states, live-send state, and startup configuration warnings. Implemented partially through safe status JSON.

### Mention laboratory

Support local, Discord, and X normalized dry runs; direct mentions and replies; bug, feature, summary, explanation, hostile, unaddressed, and duplicate cases; and show intent, response, responder, status, missing capabilities, conversation scope, and dispatch outcome. The first slice supports the shared dry-run request; raw-shaped presets are next.

### Platform controls

Discord should show token presence only, allowlisted channels, inherited-thread policy, live-send switches, private test checklist, recent event IDs, exact response targets, delivery receipts, and disabled/failure reasons. X should show credential completeness only, polling/checkpoint state, normalized conversation IDs, dry-run state, and later a controlled verification checklist. Future Slack and Teams adapters should map their channel/workspace/tenant and thread/conversation identifiers into the same normalized scope model rather than changing cognition.

### API activities

Link OpenAPI, run health and dry-run calls, inspect payloads, and generate copyable curl/PowerShell examples. Mutating or live routes must never be casually exposed as dashboard buttons.

### Uploads and downloads

Near-term, bounded UTF-8 transcript/project-note uploads for a local summarization dry run and exports of sanitized mention/audit records are architecturally reasonable. Safe diagnostics bundles, generated issue drafts, and stored session summaries can follow after redaction, file-size/type controls, and audit persistence exist. Raw log upload, arbitrary files, attachment downloading, and provider-backed image/audio processing are unsupported today.

### Event and audit viewer

After safe audit persistence exists, show received, rejected, ignored, duplicate, generated, and dispatched events with timestamp, platform, event ID, normalized scope, safe reason, and receipt. Message text should be redacted or omitted by default. This is not implemented yet.

### Configuration manager

Read-only readiness is appropriate now. Editing `.env` in the browser, revealing values, or enabling live send is not. A later guided configuration flow may produce instructions and require explicit confirmation, authentication, and restart semantics.

### Docs and roadmap

Render or link the audit, runbook, roadmap, known limitations, next milestone, and private test checklists. Repository-file links need a safe server route before browser rendering.

### Future voice lab

Deferred. A controlled lab may eventually show Discord voice readiness, local audio-device checks, consent notice, fixture transcription, TTS tests, turn-taking, and session logs. It requires verified Discord voice transport, OS devices, optional audio extras/models, size/time limits, and consent policy. Voice-print or biometric recognition is out of scope.

## Cross-platform interaction contract

Shared intelligence consumes normalized events with stable event, actor, platform, conversation scope, parent lineage, attachments, and an opaque response-target identity. Each adapter owns authorization, mention syntax, formatting, delivery, receipts, and rate limits.

- Discord: guild + current channel/thread + parent channel; authorize a confirmed thread through its parent but reply to the thread.
- X: account/community where available + `conversation_id` + referenced post; reply to the source post.
- Slack: team + channel + `thread_ts`; reply using the thread timestamp.
- Teams: tenant/team/channel + conversation ID + `replyToId`; reply through the activity/conversation target.

This keeps intent classification, provider selection, fallback behavior, safety, duplicate handling, and audit semantics platform-neutral while allowing platform-specific permissions and message formats.

Official interaction-model references used for this contract: Discord's thread documentation (`https://docs.discord.com/developers/topics/threads`), X conversation IDs (`https://docs.x.com/x-api/fundamentals/conversation-id`), Slack `app_mention` events (`https://api.slack.com/events/app_mention`), and Microsoft Teams bot conversations (`https://learn.microsoft.com/en-us/microsoftteams/platform/bots/build-conversational-capability`). These establish adapter requirements; they do not mean Slack or Teams adapters are implemented.

## Security and deployment boundary

The UI accepts only loopback/test-client requests. This is an address check, not authentication, and must not be presented as sufficient for remote deployment. A reverse proxy can change perceived client addresses; remote deployment requires real authentication, CSRF protection, secure cookies, authorization roles, TLS, and an explicit trusted-proxy policy. Secrets remain server-side and only presence/completeness booleans may reach the browser.

## Acceptance path

Next GUI work should add raw platform presets, safe route discovery, and an audit viewer only after audit persistence exists. A separate frontend is justified only when component complexity, authenticated multi-user operation, or remote deployment becomes a real requirement.
