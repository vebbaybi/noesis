# Provider Routing

Current routing supports local deterministic fallback, OpenAI-backed local provider behavior, and optional ELKA with fallback. OpenAI and ELKA are credential-gated and not required for local interpretation, memory, or deterministic responses.

The requested routing modes (`deterministic_only`, `local_only`, `local_first`, `external_enhanced`, `external_explicit`) are not yet implemented as configuration because no local generative backend exists. Adding dead modes would misrepresent readiness. Before external calls receive memory or platform context, a privacy classification and sanitization policy must be implemented.
