# Local Cognition

Noesis includes a dependency-free `LocalNLP` interpreter. It returns language (`en` or `und`), intent, confidence, dialogue act, entities, topics, sentiment, emotion, urgency, toxicity signal, humor opportunity, clarification need, and the explicit `heuristic_local_nlp` limitation.

Supported high-confidence deterministic intents include memory write/forget phrasing, current platform context, bug reports, feature requests, summarization, help, and greetings. Unknown statements are low-confidence. This is heuristic classification, not a trained model, and no accuracy claim is made without an evaluation dataset.

Provider generation remains optional. This host was classified `deterministic_only` because it has approximately 5.9 GiB RAM and two logical CPUs. No model was downloaded. A future local backend needs an explicit model path, license/checksum review, bounded worker concurrency, cancellation, and resource benchmarks.
