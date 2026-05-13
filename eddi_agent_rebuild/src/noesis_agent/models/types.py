from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field


def normalize_platform(value: Any) -> str:
    if value is None:
        return "dual"

    normalized = str(value).strip().lower()

    known_x = {"x", "twitter", "x space", "x spaces", "xspace", "twitter space", "spaces"}
    known_discord = {"discord", "discord voice", "voice channel"}

    if normalized in known_x:
        return "x"
    if normalized in known_discord:
        return "discord"
    if normalized in {"both", "dual", "x+discord", "cross"}:
        return "dual"

    raise ValueError(
        f"Invalid platform value. Got: {value!r}\n"
        "Expected one of: x / twitter / spaces, discord / voice, dual / both"
    )


Platform = Annotated[str, Field(validate_default=True)]
LengthPreset = Literal["short", "medium", "long"]
SpeakerRole = Literal["host", "cohost", "guest", "audience", "system", "bot"]
SessionStatus = Literal["created", "scheduled", "live", "ended", "cancelled", "failed"]
PlatformStatus = Literal["pending", "live", "ended", "error"]
RecordingStatus = Literal["none", "active", "completed", "failed"]
ChainId = Literal["bitcoin", "ethereum", "solana", "base", "polygon", "arbitrum", "optimism", "other"]


__all__ = [
    "ChainId",
    "LengthPreset",
    "Platform",
    "PlatformStatus",
    "RecordingStatus",
    "SessionStatus",
    "SpeakerRole",
    "normalize_platform",
]
