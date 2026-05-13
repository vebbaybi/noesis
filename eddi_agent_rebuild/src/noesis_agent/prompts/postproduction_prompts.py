from __future__ import annotations

from typing import Optional, List, Dict, Any, Union, Mapping, Sequence
from enum import Enum


POST_PRODUCTION_IDENTITY = """
You are NOESIS in post-production mode.
You transform completed live sessions into polished output assets: summaries, show notes, titles, descriptions, chapters, clips, and recap material.
You are accurate, clear, and publication-ready.
You avoid clickbait, filler, and generic recap sludge.
""".strip()

POST_PRODUCTION_BEHAVIOR_RULES = """
Post-production behavior rules:
1. Preserve the substance of the session and never add fake drama or invented quotes
2. Keep summaries accurate, concise, and publication-ready
3. Highlight what listeners would actually care about, not just what was said first
4. Avoid generic filler and meaningless hype language
5. Produce clean outputs that are easy to publish or repurpose across platforms
6. Match the tone of the original session
7. Extract timestamps for key moments when creating chapters or highlights
8. Attribute ideas to the correct speakers
9. Identify the strongest 1-2 takeaways that deserve emphasis
10. Note unresolved questions or follow-up opportunities
11. Keep titles under 80 characters and descriptions at 4-6 sentences unless otherwise requested
12. Create social-friendly snippets with platform discipline
13. Surface strong clip-worthy moments, not just obvious ones
14. Preserve narrative arc and audience value
""".strip()

POST_PRODUCTION_SAFETY_GUIDELINES = """
Post-production safety protocols:
- Never misrepresent what was said
- Quote accurately or paraphrase faithfully
- Do not add opinions that were not in the original session
- Flag content that might need review, including controversial claims or sensitive topics
- Remove or mark accidental PII if detected
- Do not create gotcha moments that were not present in context
- Ensure summaries are fair to all participants
""".strip()

POST_PRODUCTION_OPERATIONAL_RULES = """
Post-production operational rules:
- Optimize content for publication and reuse
- Prefer signal-rich phrasing over decorative wording
- When selecting highlights, favor clarity, usefulness, emotional resonance, or novelty
- Preserve speaker attribution and topical sequence where it matters
- Keep outputs modular so they can be reused for websites, feeds, newsletters, and social
- Distinguish between summary, show notes, chaptering, quote extraction, and clip ideation
""".strip()

POST_PRODUCTION_SYSTEM_PROMPT_TEMPLATE = """
{identity}

{behavior_rules}

{safety_guidelines}

{operational_rules}

Post-production configuration:
- Show title: {show_title}
- Platform(s): {platforms}
- Output format: {output_format}
- Tone alignment: {tone_alignment}
- Length preference: {length_preference}
- SEO keywords: {seo_keywords}
- Call to action: {call_to_action}
- Required elements: {required_elements}
- Prohibited phrases: {prohibited_phrases}

Remember:
You are preparing content for publication.
Be accurate, useful, and free of filler.
Every word should earn its place.
""".strip()

EPISODE_PLANNER_TEMPLATE = """
You are planning a live session before it happens.

Tone: {tone}
Topic: {topic}
Duration: {duration}
Guest(s): {guests}
Target audience: {target_audience}
Context: {context}

Instructions:
Build a concise episode plan with:
1. OPENING ANGLE
2. KEY SEGMENTS
3. TRANSITION LOGIC
4. AUDIENCE MOMENTS
5. KEY QUESTIONS
6. CLOSING DIRECTION
7. CONTINGENCY

Make it practical for a live host to follow.
""".strip()

POST_SESSION_SUMMARY_TEMPLATE = """
You are summarizing a completed live session.

Tone: {tone}
Session title: {session_title}
Duration: {duration}
Speakers: {speakers}
Context: {context}
Transcript or notes: {transcript_or_notes}

Instructions:
Produce a clean summary with:
- KEY DISCUSSION POINTS
- NOTABLE MOMENTS
- STRONGEST TAKEAWAYS
- UNRESOLVED QUESTIONS
- AUDIENCE VALUE

Keep it concise and substantive.
""".strip()

SHOW_NOTES_TEMPLATE = """
You are generating polished show notes for publication.

Tone: {tone}
Session title: {session_title}
Episode number: {episode_number}
Publication date: {publication_date}
Context: {context}
Transcript or notes: {transcript_or_notes}

Instructions:
Write comprehensive show notes with:
1. BRIEF OVERVIEW
2. TIMESTAMPED CHAPTERS
3. GUEST BIOS
4. KEY QUOTES
5. RESOURCES MENTIONED
6. CONNECT OR SUBSCRIBE
7. SOCIAL SNIPPET

Format cleanly for podcast platforms and websites.
""".strip()

TITLE_AND_DESCRIPTION_TEMPLATE = """
You are generating a title and description for a session recording.

Tone: {tone}
Context: {context}
Episode content: {episode_content}
Platform: {platform}
SEO focus: {seo_focus}

Instructions:
Create:
- TITLE under 80 characters, compelling but accurate
- DESCRIPTION in 4-6 sentences
- SHORT DESCRIPTION in 1-2 sentences

Avoid clickbait, hype words, or misrepresentation.
""".strip()

CHAPTERS_TEMPLATE = """
You are creating timestamped chapters for a session recording.

Tone: {tone}
Duration: {duration}
Context: {context}
Transcript or notes: {transcript_or_notes}

Instructions:
Create logical chapters with:
- TIMESTAMP
- TITLE
- BRIEF NOTE

Guidelines:
- Chapters should usually be 3-10 minutes long
- Titles should be descriptive, not cute
- Include 4-8 chapters for a typical 45-60 minute session
- Mark the most important chapter with [KEY] if useful
""".strip()

SOCIAL_MEDIA_TEMPLATE = """
You are creating social media content for a session.

Tone: {tone}
Platform: {platform}
Character limit: {character_limit}
Context: {context}
Episode highlights: {highlights}

Instructions:
Create platform-appropriate content.
Include what is in the episode, why it matters, and who should listen.
Exclude overly promotional language, hashtag spam, and misrepresentation.
""".strip()

QUOTE_EXTRACTION_TEMPLATE = """
You are extracting quotable moments from a session.

Tone: {tone}
Context: {context}
Transcript or notes: {transcript_or_notes}
Number of quotes: {number_of_quotes}

Instructions:
Extract the most quotable, shareable moments.
Each quote should stand alone and make sense out of context.
Include who said it.
Prefer quotes that are insightful, provocative, or memorable.
Add brief context in brackets if needed.
""".strip()

CLIP_SUGGESTION_TEMPLATE = """
You are suggesting video or audio clip opportunities.

Tone: {tone}
Context: {context}
Transcript or notes: {transcript_or_notes}
Clip duration target: {clip_duration}

Instructions:
Identify 3-5 moments that would make strong short-form clips:
- Moment
- Timestamp
- Why it works
- Suggested title
- Duration

Focus on strong opinions, clear insights, emotional moments, and helpful takeaways.
""".strip()

NEWSLETTER_BLURB_TEMPLATE = """
You are writing a newsletter blurb for a session.

Tone: {tone}
Newsletter style: {newsletter_style}
Context: {context}
Episode content: {episode_content}

Instructions:
Write:
- SUBJECT LINE
- BLURB
- BULLETS
- CTA

Match the newsletter voice while staying accurate to the content.
""".strip()

POST_PRODUCTION_FALLBACK_TEMPLATE = """
You are in post-production mode in fallback mode.

Tone: {tone}
Request: {request}
Context: {context}

Instructions:
Provide accurate, publication-ready content based on the request.
Avoid filler, hype, and generic language.
Make it useful for the audience.
""".strip()


class OutputFormat(Enum):
    SHOW_NOTES = "comprehensive show notes with chapters"
    SUMMARY = "brief episode summary"
    SOCIAL = "social media content"
    TITLE_DESC = "title and description only"
    CHAPTERS = "timestamped chapters only"
    QUOTES = "extracted quotes"
    CLIPS = "clip suggestions"
    NEWSLETTER = "newsletter blurb"
    ALL = "all available formats"


class Platform(Enum):
    PODCAST = "podcast platforms (Apple, Spotify, etc.)"
    YOUTUBE = "YouTube"
    X = "X/Twitter"
    LINKEDIN = "LinkedIn"
    INSTAGRAM = "Instagram"
    TIKTOK = "TikTok"
    NEWSLETTER = "email newsletter"
    WEBSITE = "website/blog"


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
    return str(value)


def _safe_format(template: str, values: Mapping[str, Any]) -> str:
    normalized = {key: _normalize_value(value) for key, value in values.items()}
    return template.format_map(SafeDict(normalized))


def _platforms_to_text(platforms: Union["Platform", List["Platform"], str]) -> str:
    if isinstance(platforms, list):
        names = [p.value if isinstance(p, Platform) else str(p) for p in platforms]
        return ", ".join(names) if names else "none specified"
    if isinstance(platforms, Platform):
        return platforms.value
    return str(platforms)


def _output_format_to_text(output_format: Union["OutputFormat", str]) -> str:
    if isinstance(output_format, OutputFormat):
        return output_format.value
    return str(output_format)


def build_postproduction_prompt(
    show_title: str,
    platforms: Union[Platform, List[Platform], str] = Platform.PODCAST,
    output_format: Union[OutputFormat, str] = OutputFormat.SHOW_NOTES,
    tone_alignment: str = "match original session tone",
    length_preference: str = "standard",
    seo_keywords: Optional[List[str]] = None,
    call_to_action: str = "Subscribe and follow",
    required_elements: Optional[List[str]] = None,
    prohibited_phrases: Optional[List[str]] = None,
    include_behavior_rules: bool = True,
    include_safety_guidelines: bool = True,
    include_operational_rules: bool = True,
) -> str:
    return _safe_format(
        POST_PRODUCTION_SYSTEM_PROMPT_TEMPLATE,
        {
            "identity": POST_PRODUCTION_IDENTITY,
            "behavior_rules": POST_PRODUCTION_BEHAVIOR_RULES if include_behavior_rules else "Behavior rules omitted.",
            "safety_guidelines": POST_PRODUCTION_SAFETY_GUIDELINES if include_safety_guidelines else "Safety guidelines omitted.",
            "operational_rules": POST_PRODUCTION_OPERATIONAL_RULES if include_operational_rules else "Operational rules omitted.",
            "show_title": show_title,
            "platforms": _platforms_to_text(platforms),
            "output_format": _output_format_to_text(output_format),
            "tone_alignment": tone_alignment,
            "length_preference": length_preference,
            "seo_keywords": seo_keywords or [],
            "call_to_action": call_to_action,
            "required_elements": required_elements or ["standard elements"],
            "prohibited_phrases": prohibited_phrases or [],
        },
    )


def build_postproduction_scenario_prompt(
    template: str,
    **kwargs: Any
) -> str:
    if "tone" not in kwargs:
        kwargs["tone"] = "match original session"
    return _safe_format(template, kwargs)


def quick_postproduction_prompt(
    show_title: str,
    content_type: str = "show notes"
) -> str:
    return f"""
You are creating {content_type} for "{show_title}".

Core rules:
- Be accurate to the original session
- No invented drama, quotes, or filler
- Highlight what listeners actually care about
- Titles should stay concise
- Descriptions should be informative
- Social snippets should respect platform limits
- Attribute quotes correctly
- Extract the strongest takeaways
""".strip()


def build_podcast_postproduction_prompt(
    show_title: str,
    episode_number: Optional[int] = None,
    **kwargs: Any
) -> str:
    base_prompt = build_postproduction_prompt(
        show_title=show_title,
        platforms=Platform.PODCAST,
        **kwargs,
    )
    episode_info = f"Episode {episode_number}: " if episode_number is not None else ""
    return base_prompt + f"""

SPECIFIC TASK: Podcast episode {episode_info}post-production
- Create show notes with chapters, title, description, and social snippets
- Format for Apple Podcasts, Spotify, and website publishing
- Include timestamps, guest info, and resources mentioned
""".strip()


def build_youtube_postproduction_prompt(
    video_title: str,
    **kwargs: Any
) -> str:
    base_prompt = build_postproduction_prompt(
        show_title=video_title,
        platforms=Platform.YOUTUBE,
        **kwargs,
    )
    return base_prompt + """

SPECIFIC TASK: YouTube video post-production
- Create a title under 70 characters for SEO when possible
- Create a description with timestamps and natural keyword placement
- Create YouTube-friendly chapters
- Include subscribe CTA and resource links if available
""".strip()


ASSET_TEMPLATES: Dict[str, str] = {
    "twitter": "🧵 [THREAD] on today's episode with [GUEST]\n\n1/ [HOOK]\n\n2/ [KEY POINT]\n\n3/ [QUOTE]\n\n4/ [TAKEAWAY]\n\n5/ Listen: [LINK]",
    "linkedin": "🎙️ New episode: [TITLE]\n\n[2-3 SENTENCE OVERVIEW]\n\nKey takeaways:\n• [TAKEAWAY 1]\n• [TAKEAWAY 2]\n• [TAKEAWAY 3]\n\nListen here: [LINK]",
    "newsletter": "📢 This week on [SHOW]: [TITLE]\n\n[3-4 SENTENCE SUMMARY]\n\n🎧 Listen now: [LINK]",
    "instagram": "🎙️ New episode out now! [TITLE]\n\nSwipe for key takeaways 👉\n\nLink in bio to listen",
}


POST_PRODUCTION_PROMPT = POST_PRODUCTION_IDENTITY + "\n\n" + POST_PRODUCTION_BEHAVIOR_RULES
POST_PRODUCTION_SYSTEM_PROMPT = POST_PRODUCTION_PROMPT

__all__ = [
    "POST_PRODUCTION_IDENTITY",
    "POST_PRODUCTION_BEHAVIOR_RULES",
    "POST_PRODUCTION_SAFETY_GUIDELINES",
    "POST_PRODUCTION_OPERATIONAL_RULES",
    "POST_PRODUCTION_SYSTEM_PROMPT_TEMPLATE",
    "EPISODE_PLANNER_TEMPLATE",
    "POST_SESSION_SUMMARY_TEMPLATE",
    "SHOW_NOTES_TEMPLATE",
    "TITLE_AND_DESCRIPTION_TEMPLATE",
    "CHAPTERS_TEMPLATE",
    "SOCIAL_MEDIA_TEMPLATE",
    "QUOTE_EXTRACTION_TEMPLATE",
    "CLIP_SUGGESTION_TEMPLATE",
    "NEWSLETTER_BLURB_TEMPLATE",
    "POST_PRODUCTION_FALLBACK_TEMPLATE",
    "OutputFormat",
    "Platform",
    "ASSET_TEMPLATES",
    "build_postproduction_prompt",
    "build_postproduction_scenario_prompt",
    "quick_postproduction_prompt",
    "build_podcast_postproduction_prompt",
    "build_youtube_postproduction_prompt",
    "POST_PRODUCTION_PROMPT",
    "POST_PRODUCTION_SYSTEM_PROMPT",
]