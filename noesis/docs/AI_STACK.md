# Intelligence stack

Live text enters `application.intelligence.IntelligencePipeline`. The path claims the event id,
moderates inbound text, retrieves tenant-filtered context, asks the configured local-first router for
a discriminated structured outcome, validates and authorizes any allowlisted tool, moderates outbound
text, and then indexes the response. Discord and other boundary objects never enter this contract.

The default provider order is the local OpenAI-compatible endpoint, optional OpenAI fallback, then a
deterministic acknowledgement. LiteLLM retries are disabled; Noesis owns the bounded retry budget and
circuit cooldown. Remote fallback is disabled unless explicitly configured. Malformed structured
output is a provider failure and is never partially executed.

Tools declare Pydantic argument/result models, capability authorization, timeout and side-effect
classification. There is no arbitrary shell, filesystem, HTTP or Python tool.
