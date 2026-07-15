from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ImplementationState = Literal[
    "implemented_tested", "implemented_live_validation_required", "partial", "planned",
    "blocked_credentials", "blocked_permissions", "blocked_platform", "blocked_hardware", "unsupported",
]


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    display_name: str
    description: str
    platforms: tuple[str, ...]
    required_event_types: tuple[str, ...]
    required_permissions: tuple[str, ...]
    required_tools: tuple[str, ...]
    required_memory_types: tuple[str, ...]
    required_providers: tuple[str, ...]
    local_only_supported: bool
    live_network_required: bool
    voice_required: bool
    human_approval_required: bool
    privacy_classification: str
    training_eligible: bool
    implementation_state: ImplementationState
    validation_state: str
    known_limitations: tuple[str, ...]
    operator_status: str
    handler_ids: tuple[str, ...] = ()
    source_requirement_count: int = 0

    def safe_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RequirementTrace:
    requirement_id: str
    capability_id: str
    description: str
    source_section: str


def _cap(capability_id: str, name: str, platforms: tuple[str, ...], state: ImplementationState,
         *, handlers: tuple[str, ...] = (), tools: tuple[str, ...] = (), memory: tuple[str, ...] = (),
         permissions: tuple[str, ...] = ("authorized_scope",), limitation: str = "") -> Capability:
    external = any(platform in {"x", "spaces"} for platform in platforms)
    return Capability(
        capability_id=capability_id, display_name=name, description=name, platforms=platforms,
        required_event_types=("normalized_event",), required_permissions=permissions,
        required_tools=tools, required_memory_types=memory, required_providers=(),
        local_only_supported=not external, live_network_required=external,
        voice_required="spaces" in platforms, human_approval_required="moderation" in capability_id,
        privacy_classification="community_scoped", training_eligible=False,
        implementation_state=state,
        validation_state="offline_tested" if state == "implemented_tested" else
                         "requires_live_validation" if state == "implemented_live_validation_required" else
                         "not_fully_validated",
        known_limitations=(limitation,) if limitation else (), operator_status=state.replace("_", " "),
        handler_ids=handlers,
    )


BASE_CAPABILITIES = (
    _cap("discord.guild.owner", "Current Discord server owner", ("discord",), "implemented_live_validation_required",
         handlers=("noesis_agent.integrations.discord.tools.DiscordContextTool",), tools=("discord.current_context",)),
    _cap("discord.guild.member_count", "Discord server member count", ("discord",), "implemented_live_validation_required",
         handlers=("noesis_agent.integrations.discord.tools.DiscordContextTool",), tools=("discord.current_context",)),
    _cap("discord.channel.visible_members", "Discord channel-visible members", ("discord",), "partial",
         handlers=("noesis_agent.integrations.discord.tools.DiscordContextTool",), tools=("discord.current_context",),
         limitation="Requires a complete member cache and permission-overwrite evaluation."),
    _cap("discord.channel.context", "Discord channel context", ("discord",), "implemented_live_validation_required",
         handlers=("noesis_agent.integrations.discord.tools.DiscordContextTool",), tools=("discord.current_context",)),
    _cap("discord.thread.context", "Discord thread context and routing", ("discord",), "implemented_tested",
         handlers=("noesis_agent.integrations.discord.authorization.authorize_discord_message",), tools=("discord.current_context",)),
    _cap("discord.thread.summary", "Discord thread summarization", ("discord",), "partial",
         limitation="Bounded authorized history retrieval is not implemented."),
    _cap("discord.member.context", "Discord requesting-member context", ("discord",), "partial",
         handlers=("noesis_agent.integrations.discord.tools.DiscordContextTool",)),
    _cap("discord.support.triage", "Discord community support triage", ("discord",), "partial"),
    _cap("discord.moderation.advisory", "Advisory Discord moderation", ("discord",), "partial",
         handlers=("noesis_agent.cognition.intervention.LocalModerationClassifier",), memory=("moderation_record",)),
    _cap("memory.project_decision", "Autonomous project decisions", ("platform_neutral",), "implemented_tested",
         handlers=("noesis_agent.memory.autonomous.AutonomousMemoryService",), memory=("decision",)),
    _cap("memory.task_tracking", "Autonomous task tracking", ("platform_neutral",), "implemented_tested",
         handlers=("noesis_agent.memory.autonomous.AutonomousMemoryService",), memory=("task",)),
    _cap("memory.blocker_tracking", "Autonomous blocker tracking", ("platform_neutral",), "implemented_tested",
         handlers=("noesis_agent.memory.autonomous.AutonomousMemoryService",), memory=("blocker",)),
    _cap("memory.correction", "Correction and supersession", ("platform_neutral",), "implemented_tested",
         handlers=("noesis_agent.memory.sqlite_memory.ScopedMemoryStore",), memory=("correction", "fact")),
    _cap("memory.open_questions", "Open-question memory", ("platform_neutral",), "partial",
         handlers=("noesis_agent.memory.autonomous.CandidateExtractor",), memory=("question",)),
    _cap("memory.community_vocabulary", "Scoped community vocabulary", ("platform_neutral",), "partial",
         handlers=("noesis_agent.memory.autonomous.CandidateExtractor",), memory=("preference",)),
    _cap("memory.relationships", "People/project/task relationships", ("platform_neutral",), "planned"),
    _cap("community.explanation", "Community explanation and clarification", ("platform_neutral",), "partial",
         handlers=("noesis_agent.cognition.nlu.interpreter.LocalNLP",)),
    _cap("community.onboarding", "Community onboarding and navigation", ("platform_neutral",), "planned"),
    _cap("community.social", "Community social and cultural assistance", ("platform_neutral",), "planned"),
    _cap("community.translation", "Translation and accessibility", ("platform_neutral",), "planned"),
    _cap("project.collaboration", "Project collaboration intelligence", ("platform_neutral",), "partial"),
    _cap("research.evidence", "Evidence-backed research", ("platform_neutral",), "planned"),
    _cap("web3.intelligence", "Web3 and governance intelligence", ("platform_neutral",), "planned"),
    _cap("x.conversation", "X conversation intelligence", ("x",), "blocked_credentials",
         handlers=("noesis_agent.domain.entities.platform_events.XEventContract",), limitation="Live X credentials are unavailable."),
    _cap("x.content", "X content assistance", ("x",), "blocked_credentials",
         limitation="Live X credentials are unavailable."),
    _cap("x.risk", "X scam and risk signals", ("x",), "blocked_credentials",
         limitation="Live X credentials are unavailable."),
    _cap("spaces.live.copilot", "X Spaces live copilot", ("spaces",), "blocked_platform",
         handlers=("noesis_agent.domain.entities.platform_events.SpaceEventContract",), limitation="No verified live Spaces ingestion API is connected."),
    _cap("spaces.post_show", "X Spaces post-show artifacts", ("spaces",), "partial"),
    _cap("cross_platform.continuity", "Cross-platform project continuity", ("cross_platform",), "planned"),
    _cap("operator.runtime", "Local operator runtime visibility", ("local",), "implemented_tested",
         handlers=("noesis_agent.interfaces.api.operator.operator_status",)),
    _cap("operator.cognition", "Local dry-run cognition inspection", ("local",), "implemented_tested",
         handlers=("noesis_agent.interfaces.api.operator.inspect_cognition",)),
)


class CapabilityRegistry:
    """Grouped product capabilities plus one-to-one traceability for catalogue requirements."""

    def __init__(self, catalogue: Path) -> None:
        self.catalogue = catalogue
        self.requirements = self._parse_requirements()
        counts: dict[str, int] = {}
        for requirement in self.requirements:
            counts[requirement.capability_id] = counts.get(requirement.capability_id, 0) + 1
        self.capabilities = [Capability(**{**asdict(item), "source_requirement_count": counts.get(item.capability_id, 0)})
                             for item in BASE_CAPABILITIES]

    def _parse_requirements(self) -> list[RequirementTrace]:
        text = self.catalogue.read_text(encoding="utf-8") if self.catalogue.is_file() else ""
        section = "general"
        traces: list[RequirementTrace] = []
        for raw in text.splitlines():
            if raw.startswith("#"):
                section = self._slug(raw.lstrip("# "))
                continue
            if not raw.lstrip().startswith("*"):
                continue
            description = raw.lstrip()[1:].strip().rstrip(".")
            if len(description) < 5:
                continue
            capability_id = self._group(section, description)
            traces.append(RequirementTrace(f"req-{len(traces)+1:04d}", capability_id, description, section))
        return traces

    @staticmethod
    def _group(section: str, description: str) -> str:
        value = f"{section} {description}".lower()
        rules = (
            (r"space", "spaces.live.copilot"), (r"\bx\b|post|tweet", "x.conversation"),
            (r"cross-platform|discord to x|x to discord", "cross_platform.continuity"),
            (r"owner|owns the server", "discord.guild.owner"),
            (r"member count|members in the server", "discord.guild.member_count"),
            (r"visible|access this channel", "discord.channel.visible_members"),
            (r"thread", "discord.thread.context"), (r"channel|server", "discord.channel.context"),
            (r"moderation|harassment|spam|scam|impersonat|raid|credential|suspicious", "discord.moderation.advisory"),
            (r"decision|decided|selected approach", "memory.project_decision"),
            (r"task|assignee|deadline|action item|completed", "memory.task_tracking"),
            (r"blocker|blocked|dependency", "memory.blocker_tracking"),
            (r"correction|obsolete|contradict|changed since", "memory.correction"),
            (r"unresolved question|unanswered", "memory.open_questions"),
            (r"terminology|slang|vocabulary|abbreviation", "memory.community_vocabulary"),
            (r"relationship|who owns which|who can help|skill", "memory.relationships"),
            (r"onboard|join|contribute|correct channel|rules|documentation", "community.onboarding"),
            (r"joke|meme|humor|roast|celebrat|poll|game|reputation", "community.social"),
            (r"translat|accessible|language", "community.translation"),
            (r"research|evidence|source|verify|fact", "research.evidence"),
            (r"web3|token|protocol|governance|dao|market|treasury|chain", "web3.intelligence"),
            (r"project|release|bug|feature|sprint|pull request|repository|tester", "project.collaboration"),
            (r"explain|summar|clarif|compare|context", "community.explanation"),
        )
        return next((capability for pattern, capability in rules if re.search(pattern, value)), "community.explanation")

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        platforms: dict[str, int] = {}
        for item in self.capabilities:
            counts[item.implementation_state] = counts.get(item.implementation_state, 0) + 1
            for platform in item.platforms:
                platforms[platform] = platforms.get(platform, 0) + 1
        return {"total": len(self.capabilities), "requirement_total": len(self.requirements),
                "states": counts, "platforms": platforms}

    def route(self, *, platform: str, text: str, intent: str) -> dict:
        lower = text.lower()
        semantic_matches: list[tuple[str, str | None]] = []
        if platform == "discord":
            if re.search(r"\b(who (?:owns|runs)|server owner|guild owner|who created)\b", lower):
                semantic_matches.append(("discord.guild.owner",
                    "Discord does not expose reliable original-creator history." if "created" in lower else None))
            if re.search(r"\b(how many|member count).*(?:see|access|channel)\b", lower):
                semantic_matches.append(("discord.channel.visible_members", None))
            elif (re.search(r"\b(how many members|member count|how many people are here)\b", lower)
                  or re.search(r"\bhow many\b.*\b(?:server|guild)\b", lower)):
                semantic_matches.append(("discord.guild.member_count", None))
            if re.search(r"\b(what|which) channel|channel is this\b", lower):
                semantic_matches.append(("discord.channel.context", None))
            if re.search(r"\b(is this|current) (?:a )?thread|thread is this\b", lower):
                semantic_matches.append(("discord.thread.context", None))
            if re.search(r"\b(cursing|harass|abusive|abuse|spam|scam|leaked? (?:a )?token|suspicious link)\b", lower):
                semantic_matches.append(("discord.moderation.advisory", None))
        if semantic_matches:
            unique = list(dict.fromkeys(capability_id for capability_id, _ in semantic_matches))
            limitations = {capability_id: limitation for capability_id, limitation in semantic_matches}
            items = [next(item for item in self.capabilities if item.capability_id == capability_id)
                     for capability_id in unique]
            return {"matches": [{"capability_id": item.capability_id, "confidence": .98,
                                  "state": item.implementation_state,
                                  "limitation": limitations[item.capability_id] or
                                                (item.known_limitations[0] if item.known_limitations else None)}
                                 for item in items],
                    "clarification_required": False,
                    "tool_plan": list(dict.fromkeys(tool for item in items for tool in item.required_tools)),
                    "platform": platform}
        tokens = set(re.findall(r"[a-z0-9]{3,}", f"{intent} {text}".lower()))
        ranked = []
        for item in self.capabilities:
            if platform not in item.platforms and "platform_neutral" not in item.platforms:
                continue
            terms = set(re.findall(r"[a-z0-9]{3,}", f"{item.display_name} {item.description}".lower()))
            score = len(tokens & terms) / max(1, len(tokens))
            if score:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        matches = ranked[:3]
        return {"matches": [{"capability_id": item.capability_id, "confidence": round(score, 3),
                              "state": item.implementation_state,
                              "limitation": item.known_limitations[0] if item.known_limitations else None}
                             for score, item in matches], "clarification_required": not matches,
                "tool_plan": [tool for _, item in matches for tool in item.required_tools], "platform": platform}

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "general"


__all__ = ["Capability", "CapabilityRegistry", "RequirementTrace"]
