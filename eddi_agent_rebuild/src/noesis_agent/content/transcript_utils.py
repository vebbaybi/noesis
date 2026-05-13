from __future__ import annotations

import re


def normalize_transcript_lines(transcript_text: str) -> list[str]:
    return [line.strip() for line in transcript_text.splitlines() if line.strip()]


def trim_text(text: str, limit: int = 180) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def extract_matching_lines(lines: list[str], pattern: str, *, limit: int = 3) -> list[str]:
    regex = re.compile(pattern, re.IGNORECASE)
    matches: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not regex.search(line):
            continue
        normalized = line.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        matches.append(trim_text(line))
        if len(matches) >= limit:
            break
    return matches


__all__ = ["extract_matching_lines", "normalize_transcript_lines", "trim_text"]
