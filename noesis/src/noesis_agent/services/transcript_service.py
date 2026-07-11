from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from noesis_agent.models.runtime import ActionItem
from noesis_agent.models.transcript import SessionTranscriptEvent, TranscriptEvent


class TranscriptService:
    """Normalizes transcript events and derives lightweight session artifacts."""

    def normalize_event(self, session_id: str, event: SessionTranscriptEvent | TranscriptEvent) -> TranscriptEvent:
        content = event.content.strip()
        normalized = event.model_copy(
            update={
                "session_id": session_id,
                "content": content,
                "timestamp": event.timestamp or datetime.now(timezone.utc),
            }
        )
        payload = normalized.model_dump(mode="json")
        payload.pop("text", None)
        return TranscriptEvent.model_validate(payload)

    def render_text(self, events: Iterable[TranscriptEvent], *, include_timestamps: bool = False) -> str:
        lines: list[str] = []
        for event in events:
            speaker = event.speaker or event.role
            prefix = f"[{event.timestamp.isoformat()}] " if include_timestamps else ""
            lines.append(f"{prefix}{speaker}: {event.content}")
        return "\n".join(lines)

    def tail(self, events: list[TranscriptEvent], limit: int = 12) -> list[TranscriptEvent]:
        return events[-max(0, limit) :]

    def speaker_counts(self, events: Iterable[TranscriptEvent]) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for event in events:
            counts[event.speaker or event.role] += 1
        return dict(counts)

    def action_items(self, events: Iterable[TranscriptEvent]) -> list[ActionItem]:
        items: list[ActionItem] = []
        triggers = ("todo:", "action:", "follow up:", "follow-up:")
        for event in events:
            text = event.content.strip()
            lower = text.lower()
            for trigger in triggers:
                if trigger in lower:
                    description = text[lower.index(trigger) + len(trigger) :].strip(" -:")
                    if description:
                        items.append(
                            ActionItem(
                                description=description[:500],
                                owner=event.speaker,
                                source_event_id=event.event_id,
                            )
                        )
                    break
        return items


__all__ = ["TranscriptService"]
