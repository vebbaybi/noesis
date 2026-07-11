from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PublishingManifest:
    title: str
    description: str
    audio_path: str | None = None
    transcript_path: str | None = None
    cover_prompt: str | None = None


class PublishingManifestBuilder:
    def build(self, title: str, description: str, audio_path: str | None = None, transcript_path: str | None = None) -> PublishingManifest:
        return PublishingManifest(
            title=title,
            description=description,
            audio_path=audio_path,
            transcript_path=transcript_path,
            cover_prompt=f"Cover art for {title}",
        )
