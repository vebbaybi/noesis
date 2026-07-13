# Operator Guide

Run `python -m noesis_agent.runner` and open `http://127.0.0.1:8000/`. The local operator shows runtime/storage/provider/memory readiness and offers dry-run cognition inspection. Storage is represented by label and configured/available/writable state; exact host paths and secret values are excluded.

The interface is loopback-restricted, not authenticated. Do not expose it remotely. Model, memory mutation, connector, dataset, training, destructive, and live-send controls are not implemented and must not be inferred from navigation labels.
