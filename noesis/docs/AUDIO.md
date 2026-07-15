# Audio

Audio remains an optional extra. Existing Faster Whisper and voice adapters use lazy imports and worker
boundaries; transcribed Discord audio is normalized before cognition. Generated speech must only be
called after outbound moderation in new flows. No live voice environment, ElevenLabs credentials, or
supported X Spaces broadcast API was available, so those capabilities remain credential/platform
blocked rather than reported operational.

The retained streaming path has a 64-chunk input bound, performs the lazy Faster Whisper generator
consumption in a worker thread, propagates task cancellation, and keeps PCM in memory (it creates no
temporary transcription files). Recorder filenames are path-sanitized and its WAV contract is fixture
tested. Runtime shutdown stops the streaming task through its sentinel before adapter shutdown.

The base package imports without Faster Whisper. Constructing `TranscriptionPipeline` without the
`audio` extra raises an actionable dependency error; construction is therefore not reported as model
readiness. Listener queues are process-local and audio contents are excluded from health/operator
payloads. Actual STT/TTS model loading, audio-device I/O, Discord voice, and X Spaces remain unvalidated.
