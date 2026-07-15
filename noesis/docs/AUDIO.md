# Audio

Audio remains an optional extra. Existing Faster Whisper and voice adapters use lazy imports and worker
boundaries; transcribed Discord audio is normalized before cognition. Generated speech must only be
called after outbound moderation in new flows. No live voice environment, ElevenLabs credentials, or
supported X Spaces broadcast API was available, so those capabilities remain credential/platform
blocked rather than reported operational.
