# Validation ledger

| Capability | Highest verified level | Current blocker |
| --- | --- | --- |
| Active Discord mention path | Local end-to-end with runtime composition | Live guild credentials |
| Discord commands/views/modal | Construction and application integration | Live guild credentials |
| Detoxify `original` CPU model | Real local model inference | GPU unvalidated |
| FastEmbed and Qdrant | Real embedding plus in-memory Qdrant integration | External Qdrant service unavailable locally |
| Redis | Construction, degradation and CI service harness | No local Redis service/Docker |
| Local LLM | Construction and controlled-failure tests | No compatible endpoint running |
| Remote OpenAI fallback | Policy/unit tests | Credentials and explicit authorization |
| Docker CPU profile | Static YAML/config review and executable CI job | Docker unavailable locally; CI not yet executed |
| Audio | Base import and retained optional boundaries | Hardware/provider credentials |
| X Spaces | Contract only | Supported authorized platform API unavailable |

Construction, unit, integration, local end-to-end, real local service, and live platform validation are
reported separately. Test doubles are never recorded as live services.
