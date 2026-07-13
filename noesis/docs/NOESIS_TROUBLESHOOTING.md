# Troubleshooting

- Run the complete system with `python -m noesis_agent.runner`; direct Uvicorn is API/UI development mode only.
- Browse to `127.0.0.1`, never `0.0.0.0`.
- Missing Discord/X/OpenAI credentials should produce disabled/degraded states, not crashes.
- If SQLite integrity is false, stop Noesis, preserve the database and WAL/SHM files, and restore from a verified backup; do not delete production data blindly.
- Slow test startup in a OneDrive workspace can be filesystem synchronization overhead. The implemented tests may still complete normally; move a disposable clone to a local non-synchronized path for performance diagnosis.
- Live model, connector, voice, and platform behavior cannot be debugged through offline tests without their explicit dependencies and credentials.
