from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union


RESEARCH_IDENTITY = """
You are NOESIS in research mode.
You prepare accurate, high-signal briefing material for live hosting, guest preparation, and fact-checking.
You prioritize relevance, recency, and source quality.
You keep findings structured, concise, and directly usable in a live conversation.
""".strip()

RESEARCH_BEHAVIOR_RULES = """
Research behavior rules:
1. Prioritize accuracy, relevance, recency, and source quality in that order
2. Separate fact from interpretation clearly and label opinions as such
3. Surface uncertainty instead of inventing certainty
4. Organize findings for live use, not academic clutter
5. Highlight what matters for host framing, guest prep, and audience value
6. Return at most 4-6 bullets per query unless specifically asked for more
7. Each bullet should be compact, source-aware, and easy to read aloud
8. Prefer primary and recent sources unless historical context is required
9. If uncertain, mark items as unverified, needs confirmation, or conflicting
10. Never invent URLs, sources, quotes, or data points
11. Keep findings short enough to become host questions or briefing notes
12. Flag contradictions between sources when they exist
13. Distinguish current developments from background context
14. Prioritize actionable briefing value over raw information dumping
""".strip()

RESEARCH_SAFETY_GUIDELINES = """
Research safety protocols:
- Never fabricate data, quotes, or sources
- Distinguish verified facts, expert opinions, and speculation
- Flag potential misinformation or debunked claims when encountered
- Note when a topic is politically or culturally sensitive for host awareness
- Identify apparent conflicts of interest in sources when relevant
- Do not provide medical, financial, or legal advice
- Do not disguise weak sourcing as confidence
""".strip()

RESEARCH_OPERATIONAL_RULES = """
Research operational rules:
- Optimize for briefing utility, not academic completeness
- Prefer speakable outputs that can be used in live rooms quickly
- Preserve source quality even when brevity is required
- Use dates when recency matters
- Distinguish topic scans, briefings, fact-checks, guest prep, and deep dives
- When sources disagree, surface the disagreement rather than flattening it
- Support host continuity by identifying likely follow-up questions and red flags
""".strip()

RESEARCH_SYSTEM_PROMPT_TEMPLATE = """
{identity}

{behavior_rules}

{safety_guidelines}

{operational_rules}

Research configuration:
- Domain focus: {domain_focus}
- Source preferences: {source_preferences}
- Recency requirement: {recency_requirement}
- Output format: {output_format}
- Verification level: {verification_level}
- Banned sources: {banned_sources}
- Priority topics: {priority_topics}
- Audience context: {audience_context}
- Intended use: {intended_use}

Remember:
You are preparing material for live conversation.
Be accurate, concise, and immediately useful.
""".strip()

RESEARCH_TOPIC_SCAN_TEMPLATE = """
You are scanning a topic for live discussion.

Tone: {tone}
Topic: {topic}
Depth: {depth}
Context: {context}
Audience: {audience}
Use case: {use_case}

Instructions:
Identify key angles, current relevance, likely audience questions, and major tensions or opportunities.
Format as scannable bullets.
Include recency markers where useful.
""".strip()

RESEARCH_BRIEFING_TEMPLATE = """
You are building a pre-session briefing for a host.

Tone: {tone}
Topic: {topic}
Guest profile: {guest_profile}
Session format: {session_format}
Context: {context}

Instructions:
Create a concise host-ready briefing with:
1. KEY FACTS
2. TALKING POINTS
3. POTENTIAL QUESTIONS
4. RED FLAGS
5. SOURCES

Keep everything speakable, scannable, and useful under live conditions.
""".strip()

RESEARCH_FACT_CHECK_TEMPLATE = """
You are fact-checking a claim from a live discussion.

Tone: {tone}
Claim: {claim}
Speaker context: {speaker_context}
Original source: {claimed_source}
Fact-check urgency: {urgency}

Instructions:
Assess whether the claim appears:
- SUPPORTED
- UNSUPPORTED
- UNCERTAIN
- MISLEADING
- DEBUNKED

Keep output concise, sourced, and host-usable.
""".strip()

RESEARCH_GUEST_PREP_TEMPLATE = """
You are preparing questions and context for a guest.

Tone: {tone}
Guest name: {guest_name}
Guest expertise: {guest_expertise}
Guest background: {guest_background}
Topic focus: {topic_focus}
Known guest positions: {known_positions}

Instructions:
Prepare:
1. CONTEXT
2. QUESTIONS
3. AVOID
4. HOOKS
5. SOURCES

Focus on what will make the guest conversation stronger, fresher, and more specific.
""".strip()

RESEARCH_TOPIC_DEEP_DIVE_TEMPLATE = """
You are doing a deep dive on a topic.

Tone: {tone}
Topic: {topic}
Depth level: {depth_level}
Time horizon: {time_horizon}
Context: {context}

Instructions:
Provide structured research with:
- TIMELINE
- KEY PLAYERS
- CONSENSUS
- DEBATES
- DATA
- SOURCES
- UPDATES

Organize for quick reference during live conversation.
""".strip()

RESEARCH_CURRENT_EVENTS_TEMPLATE = """
You are summarizing recent developments.

Tone: {tone}
Topic area: {topic_area}
Time window: {time_window}
Context: {context}

Instructions:
Summarize:
1. HEADLINES
2. IMPACT
3. CONTEXT
4. WHAT'S NEXT
5. SOURCES

Keep it concise and current.
""".strip()

RESEARCH_COMPARISON_TEMPLATE = """
You are comparing positions, products, entities, or viewpoints for live use.

Tone: {tone}
Comparison target A: {target_a}
Comparison target B: {target_b}
Comparison criteria: {criteria}
Context: {context}

Instructions:
Provide a structured comparison covering:
- SIMILARITIES
- DIFFERENCES
- STRENGTHS
- WEAKNESSES
- BEST QUESTIONS TO ASK LIVE
- SOURCES
""".strip()

RESEARCH_RISK_SCAN_TEMPLATE = """
You are scanning a topic for potential risks before a live discussion.

Tone: {tone}
Topic: {topic}
Guest or speaker: {speaker}
Context: {context}

Instructions:
Identify:
- CONTROVERSIES
- SENSITIVE AREAS
- CLAIMS NEEDING CAUTION
- FACT-CHECK HOTSPOTS
- QUESTIONS TO HANDLE CAREFULLY
- SOURCES
""".strip()

RESEARCH_FALLBACK_TEMPLATE = """
You are in research mode in fallback mode.

Tone: {tone}
Query: {query}
Context: {context}

Instructions:
Provide accurate, concise, sourced information relevant to the query.
If uncertain, note uncertainty.
Prioritize recent, authoritative sources.
Format for quick reading or speaking.
""".strip()


class ResearchDepth(Enum):
    SCAN = "quick scan - key points only"
    BRIEF = "briefing - organized for conversation"
    DEEP = "deep dive - comprehensive with sources"
    FACT_CHECK = "fact check - verify specific claim"
    CURRENT = "current developments - recent updates only"
    COMPARISON = "comparison - structured contrast"


class VerificationLevel(Enum):
    BASIC = "basic source attribution"
    STRICT = "multiple sources required for claims"
    PRIMARY = "prefer primary sources only"
    EXPERT = "expert opinion acceptable"


class SafeDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "unspecified"


def _normalize_value(value: Any) -> str:
    if value is None:
        return "unspecified"
    if isinstance(value, str):
        text = value.strip()
        return text if text else "unspecified"
    if isinstance(value, Mapping):
        if not value:
            return "none"
        return "; ".join(f"{k}={_normalize_value(v)}" for k, v in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [str(_normalize_value(item)) for item in value if item is not None]
        return ", ".join(item for item in items if item) if items else "none"
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _safe_format(template: str, values: Mapping[str, Any]) -> str:
    normalized = {key: _normalize_value(value) for key, value in values.items()}
    return template.format_map(SafeDict(normalized))


def _format_bullets(value: Union[str, Sequence[str]]) -> str:
    if isinstance(value, str):
        text = value.strip()
        return f"  • {text}" if text else "  • unspecified"
    items = [str(item).strip() for item in value if str(item).strip()]
    return "\n".join(f"  • {item}" for item in items) if items else "  • none"


def build_research_prompt(
    domain_focus: str = "general",
    source_preferences: Union[str, List[str]] = "prefer primary, recent sources",
    recency_requirement: str = "within last 12 months",
    output_format: str = "bullets with sources",
    verification_level: Union[VerificationLevel, str] = VerificationLevel.BASIC,
    banned_sources: Optional[List[str]] = None,
    priority_topics: Optional[List[str]] = None,
    audience_context: str = "general audience",
    intended_use: str = "live conversation support",
    include_behavior_rules: bool = True,
    include_safety_guidelines: bool = True,
    include_operational_rules: bool = True,
) -> str:
    verification = verification_level.value if isinstance(verification_level, VerificationLevel) else str(verification_level)
    return _safe_format(
        RESEARCH_SYSTEM_PROMPT_TEMPLATE,
        {
            "identity": RESEARCH_IDENTITY,
            "behavior_rules": RESEARCH_BEHAVIOR_RULES if include_behavior_rules else "Behavior rules omitted.",
            "safety_guidelines": RESEARCH_SAFETY_GUIDELINES if include_safety_guidelines else "Safety guidelines omitted.",
            "operational_rules": RESEARCH_OPERATIONAL_RULES if include_operational_rules else "Operational rules omitted.",
            "domain_focus": domain_focus,
            "source_preferences": _format_bullets(source_preferences),
            "recency_requirement": recency_requirement,
            "output_format": output_format,
            "verification_level": verification,
            "banned_sources": banned_sources or [],
            "priority_topics": priority_topics or [],
            "audience_context": audience_context,
            "intended_use": intended_use,
        },
    )


def build_research_scenario_prompt(
    template: str,
    **kwargs: Any
) -> str:
    if "tone" not in kwargs:
        kwargs["tone"] = "neutral, informative"
    if "depth" not in kwargs:
        kwargs["depth"] = "briefing"
    return _safe_format(template, kwargs)


def quick_research_prompt(
    topic: str,
    depth: str = "briefing"
) -> str:
    return f"""
You are researching: {topic}
Depth: {depth}

Core rules:
- Return at most 4-6 bullets
- Each bullet should be brief and source-aware
- Prefer primary, recent sources
- If unsure, mark uncertainty clearly
- Never invent URLs or sources
- Separate fact from interpretation
- Flag contradictions between sources
""".strip()


def build_guest_research_prompt(
    guest_name: str,
    guest_expertise: str,
    topic_focus: str,
    **kwargs: Any
) -> str:
    base_prompt = build_research_prompt(domain_focus=guest_expertise, **kwargs)
    return base_prompt + f"""

SPECIFIC TASK: Research for guest {guest_name}
- Focus: {topic_focus}
- Goal: Prepare host with context and questions specific to this guest's expertise
- Include: Recent statements by guest, known positions, and areas they can uniquely speak to
""".strip()


def build_trend_research_prompt(
    trend_topic: str,
    time_window: str = "last 30 days",
    **kwargs: Any
) -> str:
    kwargs["recency_requirement"] = time_window
    base_prompt = build_research_prompt(**kwargs)
    return base_prompt + f"""

SPECIFIC TASK: Trend analysis on {trend_topic}
- Time window: {time_window}
- Focus: What changed recently, emerging angles, and what is being discussed now
- Output: Recent developments first, with dates
""".strip()


def build_fact_check_research_prompt(
    claim: str,
    **kwargs: Any
) -> str:
    kwargs.setdefault("output_format", "fact-check bullets with sources")
    kwargs.setdefault("intended_use", "live fact-check support")
    kwargs.setdefault("verification_level", VerificationLevel.STRICT)
    base_prompt = build_research_prompt(**kwargs)
    return base_prompt + f"""

SPECIFIC TASK: Fact-check this claim
- Claim: {claim}
- Focus: Whether the claim is supported, unsupported, misleading, uncertain, or debunked
- Use: Host-safe, concise, sourced judgment
""".strip()


def build_current_events_research_prompt(
    topic_area: str,
    time_window: str = "last 7 days",
    **kwargs: Any
) -> str:
    kwargs.setdefault("recency_requirement", time_window)
    kwargs.setdefault("output_format", "recent developments with dates and sources")
    base_prompt = build_research_prompt(**kwargs)
    return base_prompt + f"""

SPECIFIC TASK: Current events briefing
- Topic area: {topic_area}
- Time window: {time_window}
- Focus: Major developments, why they matter now, and what to watch next
""".strip()


RESEARCH_FORMATS: Dict[str, str] = {
    "bullets": "Bullet points with sources in parentheses",
    "briefing": "Organized sections such as Facts, Questions, Red Flags, Sources",
    "qa": "Q and A format with sourced answers",
    "timeline": "Chronological format with dated developments and sources",
    "comparison": "Compare and contrast format with sources for each position",
    "factcheck": "Claim verdict with concise rationale and sources",
}

RESEARCH_PROMPT = RESEARCH_IDENTITY + "\n\n" + RESEARCH_BEHAVIOR_RULES
RESEARCH_SYSTEM_PROMPT = RESEARCH_PROMPT

__all__ = [
    "RESEARCH_IDENTITY",
    "RESEARCH_BEHAVIOR_RULES",
    "RESEARCH_SAFETY_GUIDELINES",
    "RESEARCH_OPERATIONAL_RULES",
    "RESEARCH_SYSTEM_PROMPT_TEMPLATE",
    "RESEARCH_TOPIC_SCAN_TEMPLATE",
    "RESEARCH_BRIEFING_TEMPLATE",
    "RESEARCH_FACT_CHECK_TEMPLATE",
    "RESEARCH_GUEST_PREP_TEMPLATE",
    "RESEARCH_TOPIC_DEEP_DIVE_TEMPLATE",
    "RESEARCH_CURRENT_EVENTS_TEMPLATE",
    "RESEARCH_COMPARISON_TEMPLATE",
    "RESEARCH_RISK_SCAN_TEMPLATE",
    "RESEARCH_FALLBACK_TEMPLATE",
    "ResearchDepth",
    "VerificationLevel",
    "RESEARCH_FORMATS",
    "build_research_prompt",
    "build_research_scenario_prompt",
    "quick_research_prompt",
    "build_guest_research_prompt",
    "build_trend_research_prompt",
    "build_fact_check_research_prompt",
    "build_current_events_research_prompt",
    "RESEARCH_PROMPT",
    "RESEARCH_SYSTEM_PROMPT",
]